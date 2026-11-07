"""Actual offline installer → host connection → selected-context acceptance.

Uses synthetic local project text and a disposable runtime; no model, network,
external host or third-party server is launched.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]


def validate(wheelhouse):
    wheelhouse = Path(wheelhouse).resolve()
    with tempfile.TemporaryDirectory(prefix='stratagent-onboarding-') as tmp:
        root=Path(tmp).resolve()
        project=root/'project'; project.mkdir()
        original=b'A small Python API. Tests use the existing host. No payments.\n'
        (project/'README.md').write_bytes(original)
        env={key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')}

        def run(argv, input=None):
            result=subprocess.run([str(arg) for arg in argv],cwd=root,env=env,capture_output=True,text=True,input=input,timeout=90)
            if result.returncode:
                raise RuntimeError('Offline onboarding acceptance failed: '+result.stderr[-1500:])
            return json.loads(result.stdout)

        install=[sys.executable,SOURCE/'scripts/install.py','--runtime',root/'runtime','--wheelhouse',wheelhouse,'--workspace',project,'--host','codex','--json']
        installed=run(install)
        assert not installed['project_files_changed'] and not (project/'.agents').exists()
        assert not installed['global_settings_changed']
        repeated=run(install)
        assert repeated['reused']
        shadow=root/'shadow/stratagent'
        shadow.mkdir(parents=True)
        (shadow/'__init__.py').write_text('')
        (shadow/'__main__.py').write_text('raise SystemExit(99)')
        env['PYTHONPATH']=str(shadow.parent)
        connected=run(installed['setup']['next_action']['argv'])
        assert connected['setup']['instructions']=='present' and connected['setup']['host_loading']=='not-observed'
        skill=(project/'.agents/skills/stratagent/SKILL.md').read_text()
        assert json.dumps(installed['launcher']) in skill
        cli=[*installed['launcher'],'--workspace',project]
        context=run([*cli,'context','README.md','--json'])
        accepted=run([*cli,'context','README.md','--apply','--approve',context['approval'],'--json'])
        assert accepted['saved']
        # Connection health remains valid with pre-initialization context metadata.
        assert run([*cli,'setup','--host','codex','--json'])['setup']['instructions']=='present'
        started=run([*cli,'start','Build a Python API with tests. No payments.','--host','codex','--json'])
        request=run([*cli,'next','--details','--json'])['details']['model_request']
        fit=request['fit_request']
        assert any(entry['id']=='document:README.md' for entry in fit['evidence'])
        assessment={'schema_version':1,'context_digest':fit['context_digest'],'environment_digest':fit['environment_digest'],
                    'outcome':'keep','reason':'The controlled project fixture can use the current host without additional resources.',
                    'needs':[{'need':'Implement and test the small API','quote':'Python API with tests','status':'host',
                              'reason':'No additional extension is justified in this fixture.','evidence_refs':['request','document:README.md'],'existing':[]}],
                    'coverage':[{'part_id':part['id'],'status':'covered' if i==0 else 'constraint','need_indexes':[0] if i==0 else [],
                                 'reason':'Address the requested work.' if i==0 else 'Preserve the payments exclusion.'} for i,part in enumerate(fit['request_parts'])],
                    'alternatives':['Research an extension only if a concrete gap appears.']}
        run([*cli,'session-submit',started['session_id'],'--request-id',request['request_id'],'--response-stdin'],json.dumps({'action':'assess','assessment':assessment}))
        review=run([*cli,'next','--json'])
        run(review['next_action']['argv'])
        assert run([*cli,'next','--json'])['phase']=='kept'
        assert (project/'README.md').read_bytes()==original
        assert run([*cli,'verify'])['checked']==0
        return {'ok':True,'case':'offline-installer-connection-selected-context','version':installed['version'],
                'runtime_reused':repeated['reused'],'shell_activation_required':False,'caller_pythonpath_ignored':True,'host_loading':'not-observed',
                'selected_documents':1,'user_files_preserved':1,'new_resource_files':0,'outcome':'keep',
                'synthetic_assessment':True,'model_launched':False,'network_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheelhouse',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(validate(args.wheelhouse),indent=2,sort_keys=True))

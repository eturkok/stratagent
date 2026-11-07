import copy
import tempfile
from pathlib import Path
import unittest

from stratagent.common import StratagentError
from stratagent.quality import request_parts, review_coverage, review_recommendations
from stratagent.fit import review as review_fit
from stratagent.experience import guide, render
from stratagent.orchestration import Orchestrator
from stratagent.service import Stratagent
from stratagent.context import configure
import test_fit
from test_architect import FakeRegistry
from test_runtime_research import PROMPT, model_plan
from test_stratagent import FakeGitHub


class CoverageTests(unittest.TestCase):
    def test_actual_en_tr_parts_retain_constraints_and_exact_text_ranges(self):
        for prompt in ['Build an API. Include tests; No payments.', 'Python API geliştir. Testler olsun. Ödeme sistemi istemiyorum.']:
            parts=request_parts(prompt)
            self.assertEqual(len(parts), 3)
            self.assertTrue(all(prompt[part['start']:part['end']]==part['quote'] for part in parts))
            needs=[{'quote':parts[0]['quote']}, {'quote':parts[1]['quote']}]
            coverage=[{'part_id':part['id'], 'status':'covered' if i<2 else 'constraint', 'need_indexes':[i] if i<2 else [], 'reason':'Address actual scope.'} for i,part in enumerate(parts)]
            self.assertEqual(len(review_coverage(prompt,needs,coverage)),3)
            with self.assertRaisesRegex(StratagentError,'every request part'):
                review_coverage(prompt,needs,coverage[:-1])

    def test_claimed_coverage_cannot_reuse_unrelated_quote_or_omit_a_need(self):
        prompt='Build an API. Include browser tests.'
        parts=request_parts(prompt)
        need=[{'quote':'Build an API'}]
        coverage=[{'part_id':part['id'],'status':'covered','need_indexes':[0],'reason':'Cover requested work.'} for part in parts]
        with self.assertRaisesRegex(StratagentError,'actual request part'):
            review_coverage(prompt,need,coverage)
        coverage[1].update(status='constraint',need_indexes=[])
        with self.assertRaisesRegex(StratagentError,'Every assessed need'):
            review_coverage(prompt,[*need,{'quote':'browser tests'}],coverage)

    def test_many_request_sentences_are_bounded_without_losing_text(self):
        prompt=' '.join(f'Request number {i}.' for i in range(100))
        parts=request_parts(prompt)
        self.assertLessEqual(len(parts),32)
        for i in range(100):
            self.assertTrue(any(f'Request number {i}.' in part['quote'] for part in parts))

    def test_longer_requests_can_map_each_actual_need_without_misclassifying_constraints(self):
        fixture=test_fit.FitTests()
        fixture.setUp()
        try:
            fixture.prompt=' '.join(f'Build feature {i}.' for i in range(13))
            started=fixture.start()
            assessment=fixture.assessment(started)
            assessment['needs']=[{'need':f'Feature {i}', 'quote':f'Build feature {i}', 'status':'host',
                                  'reason':'Use the host in this controlled coverage fixture.', 'evidence_refs':['request'], 'existing':[]} for i in range(13)]
            assessment['coverage']=[{'part_id':part['id'],'status':'covered','need_indexes':[i],
                                     'reason':'Account for this actual request part.'} for i,part in enumerate(started['model_request']['fit_request']['request_parts'])]
            review=review_fit(fixture.service,assessment,started['session']['id'])
            self.assertEqual(len(review['request_coverage']),13)
        finally:
            fixture.doCleanups()

    def test_selected_document_missing_or_changed_cannot_be_called_sufficient(self):
        fixture=test_fit.FitTests()
        fixture.setUp()
        try:
            (fixture.root/'README.md').write_text('Documented design.')
            selection=configure(fixture.service.ws,['README.md'])
            configure(fixture.service.ws,['README.md'],selection['approval'],True)
            (fixture.root/'README.md').unlink()
            started=fixture.start()
            with self.assertRaisesRegex(StratagentError,'Incomplete'):
                review_fit(fixture.service,fixture.assessment(started),started['session']['id'])
        finally:
            fixture.doCleanups()


class ResourceQualityTests(unittest.TestCase):
    def setUp(self):
        self.context={'skills':[{'id':'test-resource','description':'API regression testing guidance.'}], 'mcps':[]}
        self.assessment={'needs':[{'need':'API regression review','status':'gap'},{'need':'Use the current host','status':'host'}]}
        self.explanation={'kind':'skill','candidate_id':'test-resource','candidate_quote':'API regression testing','need_indexes':[0], 'reason':'Covers the evidenced regression gap.','alternative':'Use the existing host alone if no useful resource is found.'}
        self.decision={'bindings':[{'task_id':'test','skills':['test-resource'],'mcps':[], 'justifications':[self.explanation]}]}

    def test_explanations_link_actual_gaps_and_leave_unaddressed_needs_visible(self):
        report=review_recommendations(self.context,self.assessment,self.decision)
        self.assertEqual(report['resource_explanations'][0]['needs'],['API regression review'])
        self.assertFalse(report['remaining_gaps'])
        self.decision['bindings'][0].update(skills=[],justifications=[])
        self.assertEqual(review_recommendations(self.context,self.assessment,self.decision)['remaining_gaps'],[self.assessment['needs'][0]])

    def test_missing_duplicate_unrelated_and_already_covered_resource_explanations_are_rejected(self):
        for edit in [lambda b:b.update(justifications=[]),lambda b:b['justifications'].append(copy.deepcopy(self.explanation)),
                     lambda b:b['justifications'][0].update(candidate_id='another-resource'),
                     lambda b:b['justifications'][0].update(need_indexes=[1]),lambda b:b['justifications'][0].update(need_indexes=[11]), lambda b:b['justifications'][0].update(candidate_quote='Unobserved tool capability')]:
            decision=copy.deepcopy(self.decision); edit(decision['bindings'][0])
            with self.assertRaises(StratagentError):
                review_recommendations(self.context,self.assessment,decision)

    def test_identical_reviewed_bundles_are_not_installed_twice(self):
        self.context['skills']=[{'id':name,'description':'API regression testing guidance.','files':[{'path':'SKILL.md','sha256':'a'*64}]} for name in ['test-resource','duplicate']]
        binding=self.decision['bindings'][0]
        binding['skills'].append('duplicate')
        binding['justifications'].append({**self.explanation,'candidate_id':'duplicate'})
        with self.assertRaisesRegex(StratagentError,'identical reviewed file contents'):
            review_recommendations(self.context,self.assessment,self.decision)

    def test_different_reference_layout_is_not_claimed_to_be_an_identical_bundle(self):
        self.context['skills']=[{'id':name,'description':'API regression testing guidance.',
                                'files':[{'path':'SKILL.md','sha256':'a'*64}, {'path':reference,'sha256':'b'*64}]}
                               for name,reference in [('test-resource','guide.md'),('different','other.md')]]
        binding=self.decision['bindings'][0]
        binding['skills'].append('different')
        binding['justifications'].append({**self.explanation,'candidate_id':'different'})
        self.assertEqual(len(review_recommendations(self.context,self.assessment,self.decision)['resource_explanations']),2)

    def test_same_resource_can_be_reused_across_responsibilities_without_duplicate_installations(self):
        self.decision['bindings'].append({**copy.deepcopy(self.decision['bindings'][0]), 'task_id':'security'})
        self.assertEqual(len(review_recommendations(self.context,self.assessment,self.decision)['resource_explanations']),2)

    def test_actual_assessed_session_rejects_unjustified_choice_then_reviews_and_applies_valid_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=Stratagent(Path(tmp).resolve(),github=FakeGitHub(),registry=FakeRegistry())
            driver=Orchestrator(service)
            started=driver.start(PROMPT,['generic'])
            fit=started['model_request']['fit_request']
            assessment={'schema_version':1,'context_digest':fit['context_digest'],'environment_digest':fit['environment_digest'],
                        'outcome':'research','reason':'Research the actual retrieval gap before choosing tools.',
                        'needs':[{'need':'Retrieval tooling','quote':'Qdrant retrieval API','status':'gap','reason':'Current coverage is not established.','evidence_refs':['request'],'existing':[]}],
                        'coverage':[{'part_id':part['id'],'status':'covered','need_indexes':[0],'reason':'Address the retrieval request.'} for part in fit['request_parts']],
                        'alternatives':['Keep the current host if no suitable tool is found.']}
            proposal=driver.submit(started['session']['id'],started['model_request']['request_id'],{'action':'assess','assessment':assessment})
            search=driver.submit(started['session']['id'],proposal['model_request']['request_id'],{'action':'research','plan':model_plan(service,github=False)})
            compared=driver.search(started['session']['id'],search['search_review']['approval'])
            decision=copy.deepcopy(compared['model_request']['decision_request']['suggested_decision'])
            candidate=compared['model_request']['decision_request']['context']['mcps'][0]['id']
            for binding in decision['bindings']:
                binding['skills'],binding['mcps']=[],[]
            chosen=next(binding for binding in decision['bindings'] if binding['task_id']=='test')
            chosen['mcps']=[{'candidate_id':candidate,'option':0}]
            decision['evidence_refs'].append('mcp:'+candidate) if 'mcp:'+candidate not in decision['evidence_refs'] else None
            with self.assertRaisesRegex(StratagentError,'Explain each selected resource'):
                driver.submit(started['session']['id'],compared['model_request']['request_id'],{'action':'decide','decision':decision})
            self.assertFalse(service.lock()['installations'])
            current=driver.request(started['session']['id'])
            chosen['justifications']=[{'kind':'mcp','candidate_id':candidate,'option':0,'need_indexes':[0], 'candidate_quote':'Python API testing',
                                      'reason':'A controlled fixture exercises review of a gap-linked proposal; metadata does not certify retrieval capability.',
                                      'alternative':'Keep the host and defer this resource if its capabilities remain uncertain.'}]
            accepted=driver.submit(started['session']['id'],current['model_request']['request_id'],{'action':'decide','decision':decision})
            self.assertEqual(accepted['recommendation_review']['status'],'assessed')
            self.assertIn('Why each new resource is needed',render(guide(service)))
            self.assertIn({'rule':'repository-not-allowed','repo':'example/python-tools'},accepted['blueprint']['blockers'])
            # Explicit fixture operator trust remains separate from resource quality.
            service.allow('example/python-tools')
            stage=service.stage('blueprint',**driver.review(started['session']['id']))
            service.apply_stage(stage['stage_id'],stage['plan']['approval'])
            self.assertTrue(service.verify()['ok'])

# Install and use StratAgent 0.10.0

This guide applies to the **0.10.0 source checkout** containing
`scripts/install.py`. The immutable [0.9.0 preview](https://github.com/eturkok/stratagent/releases/tag/v0.9.0)
and its [versioned guide](https://github.com/eturkok/stratagent/blob/v0.9.0/docs/quickstart.md)
remain available. PyPI publication is deferred.

## Install once, without shell activation

Python 3.11+ is required. From a reviewed checkout, run:

```sh
python3 scripts/install.py --workspace /absolute/path/to/your-project --host codex
```

On Windows use `python`. Select your actual host: `codex`, `claude`, `antigravity`,
or `generic`. Without `--host`, setup asks for the target instead of installing
several integrations by default.

The helper creates an isolated runtime in the checkout's ignored
`dist/stratagent-runtime` directory, installs this source and checks its version
and dependencies. Normal installation needs network access for pinned build/runtime
requirements. It does not install a separately published StratAgent package from
PyPI, edit PATH/shell settings, activate a host or change project files.

The output gives a short instruction to copy to your coding agent, including the
exact installed launcher. No virtual-environment activation is needed. Keep the
checkout/runtime in place while a project uses that launcher.

You can choose another directory with `--runtime PATH`. Existing unmarked
Python environments are preserved. Repeated installation reuses a matching,
verified runtime; changed source/wheel input requires a reviewed `--upgrade` or a
new runtime directory. A failed install retains its runtime for inspection/retry.
Do not delete an environment simply to bypass a failed check.

For offline use, provide `--wheelhouse DIRECTORY` containing a reviewed application
wheel for this checkout and a compatible PyYAML 6.0.3 wheel. The helper checks the
application's package bytes against this checkout before installing it. It does
not authenticate arbitrary local wheels; verify their provenance separately.
Offline acceptance: `python scripts/validate_onboarding.py --wheelhouse DIRECTORY`.

## Connect, then describe the work

Tell your coding agent:

> Use StratAgent from the launcher printed by the installer. Review and connect
> its first-party instructions to this project for our current host, preserving
> existing files. Then prepare the environment for a small Python API with tests.
> No payments. Explain whether the current setup is enough before adding tools.

The agent runs `setup --host HOST --json`, reads the first-party file preview and
carries its exact connection approval. Existing authorization to perform that
connection can be used; no manual JSON or hash copying is needed. The connected
skill records its runtime launcher, so the agent can find it in a fresh shell.
Installed launchers also ignore caller PYTHONPATH and current-directory package
shadows; source-only development retains its explicit import path.

Setup distinguishes **runtime available**, **instruction files present**, and
**host loading not observed**. A host refresh may be needed for discovery. Existing
conflicting instructions are retained; review them separately instead of replacing
them or assuming that the current host loaded the new version.

## Give the assessment useful evidence

If manifest/agent-definition evidence is insufficient, ask:

> Also use README.md, docs/architecture.md and tests/test_api.py as local project
> evidence. Explain the selection, preserve my scope and don't publish their text.

Select only files that actually exist and are useful. The agent reviews
`context PATH... --json` and saves the exact authorized selection. It does not
scan every source file or execute the selected tests. Selected text remains
untrusted local evidence; the user's request controls scope. A selected document
changing invalidates old proposals. Missing/unreadable evidence stays visible.
See [selection scope and bounds](project-context.md).

## Review useful choices

The assessment maps every bounded request part to needs, a preserved constraint,
or an unknown requiring attention. For example, API work, tests and “No payments”
remain separately visible. Mapping a sentence does not prove semantic completeness
or completed application work.

- **Keep:** accept the reasons for retaining a sufficient setup; no search or new
  resource files are required.
- **Research:** concrete gaps guide queries. Each selected resource must identify
  its assessed gap, quote its actual reviewed description, explain the benefit
  and give an alternative including no addition. Exact duplicate skill bundles
  are refused; one resource can still be shared across responsibilities.
- **Uncertain or blocked:** inspect the actual missing evidence/conflict and
  preserve progress. Resource reasons cannot grant repository trust, approve
  outbound search, bypass drift or activate a tool.

The coding agent carries commands and review digests. You review the meaningful
choices and exact changes, using existing authorization where it applies.
[Recommendation review](recommendation-review.md) describes the current checks
and their limits. Real host loading and improved task outcomes remain unmeasured;
controlled fixtures are not native host sessions or human evaluations.

For project changes and destination-host summaries, use [maintenance and handoff](maintenance-handoff.md).

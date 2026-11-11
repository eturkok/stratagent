# Paired task outcome evaluation

## Actual first observation — November 11, 2026

Two separate Codex Work agent runs implemented the same original offline,
standard-library inventory CLI request. The baseline was instructed to work
without StratAgent; the assisted run used the first-party workflow and the same
inherited model. Neither received the other's implementation or the acceptance
answers. The assisted run inspected the environment, connected the reviewed
first-party instructions and accepted a no-addition assessment before coding.

| Observed result | Baseline | With StratAgent |
| --- | --- | --- |
| Fixed executable acceptance cases | 22 / 22 | 22 / 22 |
| Original README preserved | Yes | Yes |
| Additional external resources installed | 0 | 0 |
| User questions | 0 | 0 |
| First-party setup instructions and local planning state | None | Added |

The actual task-acceptance difference is **zero**. This small task did not show
a quality advantage; the assisted route involved additional setup/assessment
work. Development latency and total reasoning/call costs were not measured on a
comparable basis and no savings are claimed. Both runs created their own tests;
the fixed evaluator then ran each program in new subprocesses against the same
valid, invalid, UTF-8/BOM, strict-CSV, missing-file and file-preservation cases.

The assisted run initially started before connecting the first-party skill.
The added definition correctly made its prior project context stale; it followed
the guidance to create a deliberately fresh session. This is an observed onboarding
ordering cost, not a passing test of every native host. The packaged workflow
already directs connection before starting; the local trial used source access.

This is one maintainer-controlled task pair, not a blinded experiment, independent
user study or representative corpus. Both runs used the inherited model, but
there is no provider identity attestation and the harness does not enforce equal
generation budgets. Previously waived field trials remain waived; this small
forward test does not replace or reinstate them. Preference and retention remain
unmeasured.

## Reproduce task acceptance

The [raw acceptance record](../examples/outcomes/inventory-cli/result.json) retains
the actual source/task hashes and case-level results. Both original programs and
their task README/usage files are included beside it. Review them first: this
maintainer script **executes the two supplied local programs**. Python isolation
flags are not a security sandbox; do not point it at untrusted code.

```sh
python scripts/compare_outcomes.py --baseline examples/outcomes/inventory-cli/baseline --assisted examples/outcomes/inventory-cli/assisted --host "Codex Work" --model "same inherited model; identity not attested" --output comparison.json
```

The output must be a new file; existing evidence is never overwritten. Failed
cases and input mutations stay visible. The evaluator does not launch a model,
invent task results or turn operator-supplied labels into authenticated provenance.
Running these saved programs reproduces acceptance, not the original model calls.

For further benefit measurement, collect actual new paired tasks under the same
host, repository, request and comparable budget. Retain unfavorable/inconclusive
results and separately record elapsed development time, interventions and human
judgment. No implicit telemetry, private repository collection or new service is
introduced by this harness.

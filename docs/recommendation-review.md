# Ground recommendation choices — 0.10.0 source

This increment strengthens evidence and review. It does not establish measured
recommendation accuracy, exhaustive semantic deduplication or task-performance
gains. The current host model still makes semantic judgments.

## Account for the request

`fit_request` provides a bounded `request_parts` list from the actual user text.
Sentence/line boundaries are grouped into at most 32 spans; each retains its exact
quote/range. This is text segmentation, not an automatic requirement extractor.

New fit responses require `coverage`: each part exactly once as `covered`,
`constraint` or `unknown`, with a reason. Covered parts map to quoted need indexes;
all assessed needs must be mapped. “Covered” means accounted for in the assessment,
not that an application task or capability has passed validation. Constraints and
unknown parts cannot masquerade as covered needs. Unknown parts, unresolved needs,
ambiguous explicit requirements and incomplete selected evidence cannot be called
a sufficient setup. Human review must still catch a wrongly classified constraint
or a requirement omitted inside a span.

The ordinary fit review shows the original parts, including exclusions, alongside
needs/coverage and alternatives. Existing/host coverage retains its original
meaning: observed definitions/model judgment, not proof of native loading or task
completion. Exact operator acceptance and all existing scope/budget limits remain.

## Explain every selected resource

After an assessment, a final decision binding needs one `justifications` record
for each selected skill or MCP transport. The record includes `kind`,
`candidate_id`, optional MCP `option`, gap/unknown `need_indexes`, `candidate_quote`,
`reason` and `alternative`. The live schema is supplied in the model request.

- Explanations must match selected resources exactly once. Unknown/duplicate
  explanations and need references are rejected.
- A new resource must address an assessed gap/uncertainty. Existing/host-covered
  needs alone cannot justify another installation.
- The candidate quote must occur in its actual reviewed description. This prevents
  invented source wording, not misleading descriptions or incorrect interpretation.
- Selecting two skill candidates with identical complete reviewed relative-path/content
  inventories is refused. This narrow equality check is not a semantic
  capability score; differently worded equivalents still need review.
- Reusing one resource for multiple responsibilities is allowed. Choosing no
  external resource is valid; the review shows unaddressed gaps rather than
  inventing coverage.

The human workspace review shows resource reasons, quoted source text,
alternatives and remaining gaps. Metadata and explanations remain untrusted;
source/eligibility checks, repository trust, exact egress/stage/apply approvals,
ownership, drift and recovery remain independent. No candidate is executed or
activated. Legacy/direct decisions without an assessment remain supported and
are explicitly labelled as not assessed in the guided review.

## Compatibility and evidence

Stored fit version 1 accepts optional coverage for schema compatibility, while
new requests require it. Old assessments cannot be silently accepted as meeting
the stronger review. Context changes may require a deliberately fresh plan;
existing state/budgets and installed files are preserved, with no automatic reset
or downgrade migration.

Controlled tests cover EN/TR segmentation, omitted/incorrect request mappings,
incomplete documents, invented description quotes, unnecessary/duplicate
resources and real local request/submit/review/stage/apply behavior. The offline
installer acceptance also uses a synthetic no-addition assessment; it launches no
model or host. These checks are not substitutes for the previously waived field
trials or proof of measured recommendation quality.

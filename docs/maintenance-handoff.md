# Maintain a workspace and change hosts

`maintain` and `handoff` use bounded local evidence. They do not search, install
resources, change targets, activate hosts, or run third-party content.

## One change summary

Ask your coding agent: “Check what changed in this project and whether our agent
setup needs review.” The agent runs:

```sh
stratagent maintain --json
```

The report compares the current request, targets, renderer contracts, manifest
hashes, selected-document hashes, local definition hashes, ownership records and
policy against an explicitly recorded checkpoint. Added, changed and removed
observations appear together. Managed output bytes/modes are checked separately;
drift, missing files, incomplete observations and pending recovery need attention.

The first call reports `no-checkpoint`; it cannot reconstruct historical changes.
After reviewing the observations, the agent carries the returned digest into:

```sh
stratagent maintain --record --approve EXACT_REVIEW_DIGEST --json
```

Only `.stratagent/maintenance.json` is recorded. It contains hashes and bounded
metadata, not document bodies or private conversations. Approval binds the current
workspace, previous checkpoint and exact observations, which are rechecked under
the write lock. Repeating an unchanged checkpoint does not rewrite it. Drift,
incomplete reads, recovery and changed approvals refuse recording.

A checkpoint means “these observations were reviewed,” not “this environment is
sufficient.” Review changed needs in a new fit assessment and use the existing
stage/apply lifecycle for any file updates. Scan opt-out is preserved. The reader
stops at 16 MiB of managed output bytes; unsupported/oversized/redirected files
are reported rather than verified. The checkpoint is at most 1 MiB. No global
host settings, private chats or recursive source tree are inspected.

## Review a host handoff locally

Ask: “Prepare a handoff from Codex to Claude Code, preserving our scope.”

```sh
stratagent handoff --host claude --json
```

The inert JSON includes the original request/exclusions, installed strategy,
responsibilities, open questions, selected source provenance and output hashes,
current local evidence identity and destination renderer contract. Without an
installed blueprint it says so and invents no approved roles. Changed local
evidence is labelled separately from remote freshness, which is not revalidated.

The export excludes private conversations, selected-document bodies, approval
digests and session tokens; credential-like request/decision text refuses export.
Inspect the summary before sharing. It remains untrusted local evidence, not a
permission grant or a host configuration. No file is automatically exported or
sent anywhere. `--host` selects only the report's destination.

At the destination, inspect its environment, assess needs, review any
`revise --platforms` change, and use current research/exact file review where
required. Existing approvals do not transfer. Cross-host native behavior,
permissions, skill loading and application completion are not certified.

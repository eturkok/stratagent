# Selected project context — 0.10.0 source

Manifest and local-agent inspection remain the default. Additional README,
architecture and source/test text enters planning only through an explicit,
reviewed list of project-relative files. Selection is not recursive scanning,
permission to execute files, or authority to override the user's request.

## Review and retain a selection

An agent can inspect a proposed selection without writes/network:

```sh
stratagent context README.md docs/architecture.md tests/test_api.py --json
```

The result includes the exact bounded file text, content hashes, warnings and a
selection approval. After the particular selection is authorized, the agent uses
the same paths with `--apply --approve EXACT_APPROVAL --json`. Only
`.stratagent/context.json` selection metadata is saved. Files remain user-owned.
Use `context --json` for the current selection; `context --clear --json` previews
clearing it. Clearing requires its current exact approval and never removes files.
Humans need not handle IDs/digests; the agent carries them.

Selection can precede project initialization. It uses the existing workspace
writer/recovery boundary. Stale approvals, concurrent selection changes and pending
transactions cannot be bypassed. Existing initialization, policies, sessions and
ownership are not reset. Malformed selection metadata requires inspection.

## Scope

At most eight explicit files, 32 KiB per file and 128 KiB total are read. Text must
be UTF-8. Ordinary Markdown/text and supported source/test/config text extensions
are accepted; hidden paths, globs, directories, path traversal, credential-like
names, redirects, nonregular files and oversized/unreadable inputs are refused.
No referenced file is followed. Credential-like values and terminal/bidi controls
are withheld. This limited detection is not a universal secret detector: review
chosen text and use sanitized project documents where needed.

Metadata records only the paths. Current file bytes are re-read for planning and
included as untrusted local evidence (`document:PATH`; long paths use a hashed
ID). The analysis/fingerprint binds the observations. Research and architecture
requests can cite the selected text; architectural inferences must quote actual
text instead of invented evidence. No new LLM/API transport is introduced.

Documents cannot override prompt exclusions, grant commands/permissions, select
resources by authority, or approve search/installation. Outbound query grounding
still requires the actual user request and a separate exact egress review; no
document text is automatically sent to public search. Data supplied to an external
host model remains subject to that user's host/provider permissions.

A selected document changing invalidates old planning/research/approval context.
Unavailable or withheld files produce incomplete evidence and block a claim that
the current setup is sufficient. Full semantic understanding is not inferred from
reading text or from a matching hash. Automatic `init --no-scan-project` use skips
selected documents too; an explicit `context` request independently inspects the
operator's selected scope. Existing managed-output verification remains separate.

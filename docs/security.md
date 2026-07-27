# Security model

## Credentials never live here

No token, key, or secret is stored in this repository, in `manifest/capabilities.json`, or
in `~/.claude.json`. The repository knows only three things about each credential: **what
is required, how to detect it, and how to guide setup.**

| Service | Where the credential actually lives | How we reach it |
|---|---|---|
| GitHub | OS credential store — Git Credential Manager, or GitHub CLI's store | `config/github-mcp-headers.sh`, run at connect time |
| Figma | Claude Code's own credential store (`~/.claude/.credentials.json`) | OAuth, handled by Claude Code |
| Anything future | the OS store or an env var declared in `.env.example` | never a file in this repo |

`.env.example` documents the few optional overrides. `.env` is gitignored. On a normal
workstation you need neither: GitHub and Figma credentials are already held by the OS and
by Claude Code respectively.

## Why the GitHub token is not in a config file

The obvious implementation — `headers: { "Authorization": "Bearer ghp_..." }` in
`~/.claude.json` — writes a long-lived credential to a plaintext file that also gets
backed up, synced, and read by tooling. We rejected it.

OAuth was the preferred alternative and **does not work here**: `api.githubcopilot.com`
does not support RFC 7591 dynamic client registration, which is how Claude Code registers
itself with a remote MCP auth server. It fails with *"Incompatible auth server: does not
support dynamic client registration."*

So the server is configured with **`headersHelper`**: a script that resolves a token at
connect time and prints one JSON object. Resolution order:

1. `GITHUB_PERSONAL_ACCESS_TOKEN` — explicit override, for CI or a deliberately scoped PAT
2. `gh auth token` — GitHub CLI's secure store
3. `git credential fill` — Git Credential Manager

Properties this gives us:

- **zero credentials at rest** in any file this project controls
- the token is **never printed, logged, or written to disk** by our code
- revoking in GitHub revokes the capability immediately, with no file to clean up
- the helper prints `{}` when nothing is found, so a missing credential degrades to
  "unauthenticated" rather than breaking session startup

## Least privilege

The working credential on the reference machine carries `gist, repo, workflow`. That is
sufficient for every capability we claim: repository inspection, branches, commits, PRs,
issues, Actions/CI status, releases, and repository creation.

It deliberately does **not** carry `delete_repo` or `admin:org`. Do not add scopes to make
an error go away; find out which operation needed it and decide whether that operation
belongs in this system at all.

## Supply chain

Third-party code is admitted only after inspection, and each route is a deliberate choice:

| Route | When | Example |
|---|---|---|
| **marketplace** | first-party Anthropic plugins from the official catalog | `frontend-design`, `typescript-lsp`, `pr-review-toolkit` |
| **upstream installer** | actively maintained, first-party installer, pinning would rot | `humanizer` (MIT, 31k★) |
| **vendored** | we want *one file* out of a larger repo, or upstream moves fast enough to need review-before-update | `redesign-existing-projects` |
| **rejected** | fails inspection on size, licence, architecture, or trust | see the vault's `00_System/capabilities.md` |

Every vendored skill carries a `PROVENANCE.md` recording upstream URL, licence, vendoring
date, **what was deliberately not taken**, and the update/remove commands. Vendoring
without provenance is not allowed — `doctor` reports it as a warning.

Things that were inspected and rejected on security or architecture grounds, not quality:
a skill with **no licence file** (unvendorable), and a critique skill that spawns parallel
external critics (an orchestration layer, and an extra trust boundary).

## Public-repository readiness

This repository is written to be publishable. Before flipping visibility, re-run the audit:

- no tokens, keys, or `.env`
- no personal email addresses or usernames
- no absolute machine paths (`C:\Users\<name>\...`) — everything is resolved at runtime
- no client names, business data, or private project names
- no logs, screenshots, cached tool output, or backups (all gitignored)

Machine-specific and studio-specific content lives **outside** the managed block in
`~/.claude/CLAUDE.md`, which is not in this repository. That separation is what makes
publishing safe.

Note that the *vault* is a different matter: it contains client work and decisions and
**must stay private**. This repository only references it by an environment variable.

## What bootstrap is allowed to do

It writes to `~/.claude.json`, `~/.claude/CLAUDE.md`, `~/.claude/bin/`, `~/.claude/skills/`,
and invokes the Claude CLI to install marketplace plugins. It backs up every file it
modifies first, prints every action, and supports `--dry-run`.

It never weakens a security control to make a tool easier to reach. Notably it does **not**
set `enableAllProjectMcpServers`, which would auto-approve MCP servers belonging to any
repository later cloned into the workspace.

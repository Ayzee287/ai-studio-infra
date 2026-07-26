# AI Studio — infrastructure

Reproducible Claude Code environment: MCP servers, plugins, skills, and the capability
routing that decides when each one is used.

Clone → bootstrap → authenticate → doctor → ready.

```
git clone <this-repo> ai-studio-infra && cd ai-studio-infra
bin/studio bootstrap        # converge this machine (idempotent, backs up before writing)
bin/studio doctor           # what is healthy, what needs a human
```

On Windows use `bin\studio.cmd`.

---

## What problem this solves

A capable Claude environment is not one big install. It is four layers that drift apart:
the servers that supply tools, the plugins and skills that supply method, the routing that
decides when each fires, and the knowledge that says what is already true. Configure them
by hand across months and you get an environment only one person can rebuild — and a
capability that exists but is never selected, which is the same as no capability at all.

This repository makes that state **declarative, inspectable, and reproducible**.

## The four layers, and who owns what

| Layer | Owner | Lives in |
|---|---|---|
| **Global Claude environment** — MCP servers, plugins, skills, routing | **this repository** | `~/.claude.json`, `~/.claude/`, converged by `studio bootstrap` |
| **Knowledge** — decisions, project state, standards, history | the private **AI-Studio vault** | a separate private repository, reached via the `aistudio-retrieval` MCP server |
| **Project truth** — stack, commands, conventions, binding facts | each **project repository** | that project's `CLAUDE.md` |
| **Credentials** | the **OS credential store** | never in any repository, never in `~/.claude.json` |

The boundary that matters: **this repository describes *how Claude works*. The vault
describes *what is true*. A project describes *what is true about that project*.** Nothing
here contains client data, project history, or secrets.

## Architecture

```
manifest/capabilities.json   the desired state. DATA, not code.
studio/                      the CLI: bootstrap, doctor, onboard
  common.py                  path detection, manifest loading, reporting
  detect via common.py       nothing machine-specific is ever hardcoded
config/                      templates written onto the machine
  CLAUDE.global.md           the capability routing block
  github-mcp-headers.sh      resolves a GitHub token at connect time
skills/                      vendored skills, each with PROVENANCE.md
templates/project/           project onboarding template
docs/                        architecture, auth, security, recovery, troubleshooting
tests/                       manifest + resolution tests
```

`bootstrap` and `doctor` both read the same manifest, so they cannot disagree about what
the environment is supposed to look like. Adding a capability means editing
`manifest/capabilities.json` — see [docs/adding-a-capability.md](docs/adding-a-capability.md).

## Capability map

| Capability | Implementation | Scope |
|---|---|---|
| Browser evidence, Lighthouse, traces | `chrome-devtools` MCP | user |
| UI driving, a11y snapshots, responsive QA | `playwright` MCP | user |
| Version-accurate library docs | `context7` MCP | user |
| Component sourcing | `shadcn` MCP | user |
| Design source of record | `figma` MCP | user (OAuth) |
| Remote GitHub: repos, PRs, issues, CI, releases | `github` MCP | user (OS credential) |
| Vault retrieval / graph | `aistudio-retrieval`, `graphify-vault` MCP | user (needs vault) |
| Design direction (new UI) | `frontend-design` plugin | user |
| Design critique (existing UI) | `redesign-existing-projects` skill | user (vendored) |
| Prose finishing | `humanizer` skill | user (upstream) |
| Diff review agents | `pr-review-toolkit` plugin | user |
| Type intelligence | `typescript-lsp` plugin | user |
| Local git | `git` CLI | — |

**Git is not GitHub.** Local history belongs to `git`; anything touching a remote belongs
to the `github` MCP server. Deploys stay operator-owned and are deliberately not automated.

## Commands

| Command | Does |
|---|---|
| `studio bootstrap` | Converge the machine onto the manifest. Idempotent. Backs up every file it touches. `--dry-run` to preview. |
| `studio doctor` | Health report: `PASS` / `WARNING` / `FAIL` / `NOT CONFIGURED` / `AUTH REQUIRED`. `--fast` skips live connectivity. |
| `studio onboard [path]` | Seed a project `CLAUDE.md`. Writes no infrastructure config — projects inherit everything. |
| `studio manifest` | Print the manifest with machine variables resolved. |

`doctor` exits non-zero only when something **required** actually failed. An optional
capability that is absent is reported, not treated as a catastrophe.

## Authentication

No credential is ever stored in this repository or in `~/.claude.json`.

- **GitHub** — `config/github-mcp-headers.sh` resolves a token at connect time from
  `GITHUB_PERSONAL_ACCESS_TOKEN`, then `gh auth token`, then Git Credential Manager.
- **Figma** — OAuth, held in Claude Code's own credential store.

See [docs/authentication.md](docs/authentication.md) and [docs/security.md](docs/security.md).

## Documentation

- [Architecture](docs/architecture.md) — layers, boundaries, why user scope
- [Installation](docs/installation.md) — clean machine, step by step
- [Authentication](docs/authentication.md) — what each service needs
- [Security model](docs/security.md) — credentials, supply chain, public-readiness
- [Adding a capability](docs/adding-a-capability.md)
- [Updating](docs/updating.md) — pinned vs installed vs upstream
- [Recovery](docs/recovery.md) — the machine died; get back to work
- [Troubleshooting](docs/troubleshooting.md)

## Requirements

Python 3.10+, Git, Node 18+, Claude Code 2.1.121+. Chrome and
`typescript-language-server` are optional but unlock real capabilities. `studio doctor`
tells you which are missing and how to install each.

## Licence

MIT for the tooling in this repository. Vendored third-party skills keep their own licence
and provenance — see `skills/*/PROVENANCE.md`.

# Architecture

## The problem this shape solves

Four things have to be true at once for a Claude environment to be genuinely capable:

1. the **tools** exist and are reachable,
2. the **method** exists (skills, plugins) for judgement the model won't supply alone,
3. something tells Claude **when** each fires,
4. and the **knowledge** of what is already true is retrievable.

Miss (1) and Claude improvises. Miss (2) and it produces technically-correct mediocrity.
Miss (3) and capabilities sit installed and unused — indistinguishable from not having
them. Miss (4) and every session re-derives decisions that were already made.

This repository owns (1), (2) and (3). The private vault owns (4).

## Four layers, four owners

```
      ai-studio-infra  (this repo, may become public)
      ─ how Claude works: servers, plugins, skills, routing
              │  studio bootstrap
              ▼
      ~/.claude.json · ~/.claude/          the live machine
              │
              ├── aistudio-retrieval ──►  AI-Studio vault  (private repo)
              │                            what is TRUE: decisions, state, standards
              │
              └── project CLAUDE.md        what is true about ONE project
                                           stack, commands, binding facts
```

| Layer | Contains | Never contains |
|---|---|---|
| **ai-studio-infra** | manifest, CLI, routing template, vendored skills, docs | client data, project history, credentials, machine paths |
| **AI-Studio vault** | decisions, project state, design standards, changelog | infrastructure install logic |
| **project repo** | stack, commands, conventions, binding facts | MCP/plugin/skill config |
| **OS credential store** | tokens | — |

The rule that keeps them from bleeding: **this repo says *how Claude works*; the vault says
*what is true*; a project says *what is true about that project*.**

## Why every capability is user scope

Claude Code offers three MCP scopes: `local` (per-project, in `~/.claude.json`), `project`
(a committed `.mcp.json`), and `user` (global, in `~/.claude.json`).

This system uses **user scope for everything**, and ships no `.mcp.json` at all. That was
not the original design; it is the corrected one, and the reasons are concrete:

- **A project `.mcp.json` is only auto-approved via `enableAllProjectMcpServers`**, which
  Claude Code ≥2.1.196 honours only after a workspace-trust dialog. Without that, servers
  sit at `⏸ Pending approval` and are silently unavailable.
- **That flag is dangerous anyway**: it auto-approves the MCP servers of *any* repository
  later cloned into the workspace. Removing it strictly improves the security posture.
- **The `projects.<path>` map is keyed by path** and is case-sensitive on the Windows drive
  letter, while editors spawn agents with a lowercase drive. User scope has no path key,
  so that class of bug cannot occur.
- **The old argument for narrow scope is obsolete.** It used to be "don't load N unused
  tool schemas into every session". Since Claude Code 2.1.121, MCP tool search defers tool
  *definitions*: only names and server instructions load up front. Narrow scope now costs
  availability and buys nothing.

Consequence: **a new project inherits every capability by existing.** Onboarding writes no
infrastructure config. If you find yourself adding a `.mcp.json` to a project, that is the
regression this architecture exists to prevent.

The one deliberate exception is **directory-scoped skills**: the vault's Obsidian skills
live in the vault's own `.claude/skills/` because they are meaningless outside it. Scope
should follow genuine dependence, not habit.

## Manifest-driven, not script-driven

`manifest/capabilities.json` is data. `bootstrap` converges the machine toward it; `doctor`
reports drift from it. Because both read the same file they cannot disagree about intent —
a class of bug that plagues hand-written setup scripts.

Adding a capability is a data edit, not a code edit. See
[adding-a-capability.md](adding-a-capability.md).

Machine-specific values never appear in the manifest. `${PYTHON}`, `${VAULT}`,
`${CLAUDE_HOME}` are resolved at runtime by `studio/common.py`, which detects rather than
assumes — Git is not always under Program Files, and Claude Code's binary is usually inside
a VS Code extension directory rather than on `PATH`.

## Ownership: Git vs GitHub vs CI vs deploy

Overlapping ownership is a defect. The split:

| Responsibility | Owner |
|---|---|
| Local history: branches, commits, merges, rebases, worktrees | `git` CLI via Bash |
| Remote: repos, PRs, issues, Actions status, releases, repo creation | `github` MCP server |
| Judging a diff | `pr-review-toolkit` agents (analysis) + `github` MCP (fetch/post) |
| CI status and logs | `github` MCP (Actions toolset) |
| Deploys, domains, env vars (Vercel etc.) | **operator, out of band — deliberately not automated** |

`gh` CLI is optional. It is a convenience and an alternative credential source, never a
second source of truth.

## Safety model of `bootstrap`

- **Idempotent.** A converged machine reports `0 change(s)`. Proven by re-running.
- **Never silent.** Every action prints; `--dry-run` prints only.
- **Never clobbers.** Any file modified is first copied to `~/.claude/backups/<run>/`.
- **Never merges blindly into prose.** The global `CLAUDE.md` is edited as a delimited
  managed block; operator text outside it survives verbatim. This matters because that file
  mixes generated routing with hand-written machine notes.
- **Never writes a credential.** Not to the repo, not to `~/.claude.json`.

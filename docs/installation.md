# Installation

## Prerequisites

| Required | Why |
|---|---|
| Claude Code 2.1.121+ | the host. 2.1.121 first shipped MCP tool search |
| Git | version control; Git Bash also provides the credential-helper shell on Windows |
| Node 18+ | `npx` runs the stdio MCP servers |
| Python 3.10+ | runs this CLI and the vault MCP servers |

| Optional | Unlocks |
|---|---|
| Google Chrome | `chrome-devtools`: Lighthouse, performance traces |
| `typescript-language-server` + `typescript@5` | the `typescript-lsp` plugin |
| GitHub CLI | convenience, and an alternative credential source |
| the private AI-Studio vault | `aistudio-retrieval`, `graphify-vault` |

You do not need to pre-check any of this. `studio doctor` reports what is missing and how
to install each item.

## Install

```
git clone <ai-studio-infra> && cd ai-studio-infra
bin/studio bootstrap --dry-run     # read the plan first
bin/studio bootstrap
bin/studio doctor
```

On Windows use `bin\studio.cmd`.

Restart Claude Code afterwards so it picks up MCP and plugin changes.

## Connect the knowledge layer (optional)

```
setx STUDIO_VAULT "C:\path\to\AI-Studio"     # Windows
export STUDIO_VAULT=/path/to/AI-Studio       # POSIX
```

Without it, the two vault MCP servers report `NOT CONFIGURED` and everything else works
normally.

## Authenticate

See [authentication.md](authentication.md). Short version: `gh auth login` for GitHub;
`/mcp` then figma then Authenticate, for Figma.

## What bootstrap changed

- `~/.claude.json` — MCP servers at user scope
- `~/.claude/settings.json` — marketplace and enabled plugins
- `~/.claude/CLAUDE.md` — the managed routing block; your text outside it is preserved
- `~/.claude/skills/` — vendored skills
- `~/.claude/bin/` — the GitHub credential helper

Backups of anything modified go to `~/.claude/backups/<run-timestamp>/`.

## Onboarding a project

```
cd /path/to/project
studio onboard
```

This writes a project `CLAUDE.md` template and nothing else. Projects inherit every
capability from user scope; they need no infrastructure configuration of their own.

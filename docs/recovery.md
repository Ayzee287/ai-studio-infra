# Recovery

> *"My machine was destroyed. I have a GitHub account, this repository, and the private
> knowledge vault repository. Nothing else."*

That scenario is why this repository exists. Everything below has been executed and
verified, not designed on paper. Where a step needs a human, it is because the credential
deliberately does not live in Git.

## The two halves

| Half | Repository | Contains |
|---|---|---|
| **How Claude works** | `ai-studio-infra` (this repo) | MCP servers, plugins, skills, routing, bootstrap, health checks |
| **What is true** | the private vault (`ai-studio-vault`) | decisions, project state, standards, changelog, client knowledge |

Losing either one alone is survivable. Both are required for a full restore, and both must
have remotes. A vault with no remote is the single most likely reason a "recoverable"
environment turns out not to be.

## Full procedure, empty machine to operational

### 1. Prerequisites

Install: **Git**, **Node 18+**, **Python 3.10+**, **Claude Code**, and **Google Chrome**.
Nothing else needs to be remembered — `studio doctor` names anything missing.

### 2. Restore the environment

```
git clone https://github.com/<you>/ai-studio-infra.git
cd ai-studio-infra
bin/studio bootstrap          # Windows: bin\studio.cmd bootstrap
```

Bootstrap converges MCP servers, plugins, skills and routing, and enables
`core.longpaths` on Windows. It is idempotent: safe to re-run at any point.

> **Why longpaths matters here.** Windows' `MAX_PATH` is 260 characters and Git defaults
> `core.longpaths` to false. The vault contains 111-character paths, so a clone into a
> moderately deep directory fails with *"Filename too long"* and silently drops files. This
> was found by an actual restore test. Bootstrap sets it, which is why step 3 comes after
> step 2 rather than before.

### 3. Restore the knowledge layer

```
git clone https://github.com/<you>/ai-studio-vault.git /path/to/AI-Studio
setx STUDIO_VAULT "C:\path\to\AI-Studio"        # Windows, persistent
# export STUDIO_VAULT=/path/to/AI-Studio        # POSIX: add to your shell profile
```

Open a **new** shell so `STUDIO_VAULT` is present, then rebuild the derived graph — it is
deliberately not in Git because it is regenerable:

```
pip install "graphify[mcp]"
cd /path/to/AI-Studio
python tools/graph-resolver/resolver.py --full
```

Re-run `bin/studio bootstrap` in the infra repo so the two vault MCP servers get
registered now that the vault exists.

### 4. Authenticate

Only two credentials, neither of which can safely live in Git:

- **GitHub** — `gh auth login`, or push once over HTTPS so Git Credential Manager stores a
  credential. The MCP server reads it at connect time; nothing is written to config.
- **Figma** — in Claude Code, `/mcp` → `figma` → Authenticate.

### 5. Verify

```
bin/studio doctor
```

Then restart Claude Code and confirm from a **fresh session** that the skills and MCP
servers are present. Configuration is a claim; a fresh session is the evidence.

## Verified restore results

A real clone-and-verify of the vault, performed as if the original did not exist:

| Check | Result |
|---|---|
| `git fsck` | clean |
| HEAD equality | identical to origin |
| Commit count | 40 = 40 |
| Tracked files | 361 = 361, file lists identical |
| Working tree | 0 missing checkouts |
| Architecture docs | all present (`capability-routing`, the two constitutions, design standards) |
| Obsidian structure | `.obsidian/` present, 225 notes, 177 containing wikilinks |
| Retrieval layer rebuilt | 210 files, 2,105 links, 2,092 resolved, in 0.18s |

The last row is the one that matters most: the knowledge layer is not merely *stored*, it
is **queryable again** after restore.

## Why there is no `studio recover` command

Considered and deliberately rejected. It would be a thin wrapper over `git clone`, an
environment variable, and a script that already exists, while the steps that actually carry
risk — installing Claude Code, authenticating GitHub and Figma — cannot be automated at
all. `bootstrap` already converges everything mechanical and is idempotent, and `doctor`
names each missing piece together with its fix. A `recover` verb would add surface and
another thing to trust without removing a single genuinely hard step.

Fewer trustworthy commands beat more wrappers.

## What is deliberately NOT recoverable from Git

- **Credentials.** By design. Re-issued, never restored.
- **Derived artefacts** — `graphify-out/`, caches, `__pycache__`. Regenerated in step 3.
- **Application repositories.** Cloned from their own remotes; they are not part of this
  system and inherit every capability automatically once the environment is up.

## Recovery drill

Do this occasionally rather than trusting that it still works:

1. Clone the vault to a scratch directory.
2. `git fsck`, compare HEAD and `git ls-files | wc -l` against the live copy.
3. Rebuild the resolver graph inside the scratch copy.
4. Delete it.

Never point the live environment at the scratch copy.

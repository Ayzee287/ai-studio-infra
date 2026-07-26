# Troubleshooting

Start with `studio doctor`. It names the failing component and the fix.

## MCP servers show "Pending approval"

Something is defining them at **project** scope. This system uses user scope only. Look for
a stray `.mcp.json` in the project or a parent directory and remove it, then run
`studio bootstrap`.

Do not "fix" this by setting `enableAllProjectMcpServers`: that auto-approves the MCP
servers of any repository later cloned into the workspace.

## A tool I know is installed is not in my tool list

Expected. MCP tools are **deferred** — tool search loads only tool names and server
instructions at session start. Fetch the schema with `ToolSearch` before calling. Absence
from the visible list is not evidence of absence.

## The server is configured but this session cannot see it

MCP servers are loaded at session start. If it was added mid-session, restart Claude Code.
`claude mcp list` runs in a separate process and will happily show a server as connected
while the running session still cannot use it.

## GitHub: AUTH REQUIRED, or 401 on a call

The headers helper found no token. Create one:

```
gh auth login
```

or push once over HTTPS to populate Git Credential Manager.

Run the helper directly to check: it prints a single JSON object, and prints `{}` when no
credential is found. If it prints anything else, something is writing to stdout and
corrupting the header set.

## GitHub: "Incompatible auth server: does not support dynamic client registration"

Expected if the server is configured for OAuth. `api.githubcopilot.com` cannot do RFC 7591
registration. Use the `headersHelper` configuration shipped in the manifest instead.

## TypeScript LSP does not start

`typescript-language-server` resolves `typescript/lib/tsserver.js`, which **TypeScript 7 no
longer ships at that path**. Install a v5 line:

```
npm install -g typescript-language-server typescript@5
```

Then restart Claude Code. The LSP attaches at session start and will not recover
mid-session after a failed initialize.

## Git Bash not found on Windows

Git is not always under Program Files. Detection tries several roots; if yours is unusual,
check what it resolves to:

```
python -c "from studio.common import find_git_bash; print(find_git_bash())"
```

## graphify query fails with "graph file not found"

You are running it from a directory that has no `graphify-out/`. Point at the repo's graph:

```
graphify query "<q>" --graph <repo>/graphify-out/graph.json
```

Never run `graphify update .` from a workspace parent: it crawls every repository and every
`node_modules`.

## Bootstrap keeps reporting the same change

That is an idempotency bug; please report it. The usual causes are cosmetic differences
read as real drift: path separators, letter case, an empty `env: {}`, or CRLF translation
on write. Compare by meaning, not spelling.

## Undoing a bootstrap

Every modified file is copied to `~/.claude/backups/<run-timestamp>/` before writing. Copy
the file back and re-run `studio doctor`.

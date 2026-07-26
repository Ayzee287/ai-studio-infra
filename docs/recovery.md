# Recovery

> *"My machine died. I have a fresh Windows install, this repository, and the private vault."*

That scenario is the reason this repository exists. The path back is below; it assumes
nothing is remembered.

## Shortest reliable path

```
1. Install prerequisites          Git, Node 18+, Python 3.10+, Claude Code, Chrome
2. git clone <ai-studio-infra>    the infrastructure half
3. git clone <AI-Studio vault>    the private knowledge half
4. set STUDIO_VAULT to the vault path
5. cd ai-studio-infra
   bin/studio bootstrap           converges MCP, plugins, skills, routing
6. authenticate (below)
7. bin/studio doctor              confirm
8. Restart Claude Code
```

Step 5 is the only step that touches configuration, and it is idempotent, so it is safe to
re-run at any point.

## Authentication after a rebuild

Two credentials, neither stored in any repository:

- **GitHub** — `gh auth login`, or simply `git push` once over HTTPS so Git Credential
  Manager stores a credential. `studio doctor` reports `AUTH REQUIRED` until one exists.
- **Figma** — in Claude Code run `/mcp`, select `figma`, choose Authenticate.

Everything else (Chrome DevTools, Playwright, Context7, shadcn) needs no credential.

## Restoring the knowledge layer

The vault is a normal git repository. After cloning it:

```
pip install "graphify[mcp]"
python tools/graph-resolver/resolver.py --full      # rebuild the resolved graph
```

`doctor` reports `vault resolved graph` as a WARNING until this is built. The vault's own
post-commit hook keeps it fresh afterwards.

## If a capability is missing rather than broken

`doctor` distinguishes deliberately:

| Status | Means |
|---|---|
| `PASS` | working |
| `WARNING` | working, but degraded or drifting |
| `AUTH REQUIRED` | configured correctly, a human must authenticate |
| `NOT CONFIGURED` | optional, absent, and that is fine |
| `FAIL` | required, and broken. The only status that fails the exit code |

## What is NOT recoverable from this repository

- **Client work and project history.** That is the vault. Back it up separately.
- **Credentials.** By design. They are re-issued, never restored.
- **Application repositories.** Cloned from their own remotes.

## Verifying the rebuild honestly

Configuration files are a claim; a fresh session is the evidence. Open Claude Code in an
empty directory and ask it to list its skills and MCP servers. If that list matches
`studio manifest`, the environment is genuinely restored.

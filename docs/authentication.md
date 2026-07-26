# Authentication

Installation and authentication are separate on purpose. `studio bootstrap` never prompts
for a credential and never stores one; it only puts the *mechanism* in place. Everything
below is a human action.

## GitHub

**Needed for:** repositories, branches, PRs, issues, Actions/CI status, releases,
repository creation. Everything the `github` MCP server does.

**Where the credential lives:** the OS credential store. Never in this repository, never in
`~/.claude.json`.

**Set it up** (either is sufficient):

```
gh auth login                 # GitHub CLI's own secure store
```
or simply push once over HTTPS, which makes Git Credential Manager store a credential.

**How it is used:** `~/.claude/bin/github-mcp-headers.*` resolves a token at connect time,
in this order: `GITHUB_PERSONAL_ACCESS_TOKEN`, then `gh auth token`, then
`git credential fill`.

**Scopes:** `repo` is the minimum; add `workflow` for Actions. Do not add `delete_repo` or
`admin:org`.

**Why not OAuth:** `api.githubcopilot.com` does not support RFC 7591 dynamic client
registration, so Claude Code cannot register itself with that auth server. The headers
helper is the alternative that still keeps zero credentials at rest.

**Verify:** `studio doctor` shows `github credential: PASS`.

## Figma

**Needed for:** reading design context, meaning frames, Auto Layout, spacing, type and
variables.

**Where the credential lives:** Claude Code's own credential store.

**Set it up:** in Claude Code run `/mcp`, select `figma`, choose Authenticate, complete the
browser flow. One time per machine.

**Seat limitation:** read paths work on any seat. Write and generate paths (`use_figma`,
`generate_figma_design`, `create_new_file`) require a Dev or Full seat. On a View seat,
treat Figma as read-only.

**Verify:** `studio doctor` shows `figma credential`, and `/mcp` shows figma connected.

## Nothing else needs a credential

Chrome DevTools, Playwright, Context7 and shadcn all run unauthenticated. The vault servers
read local files. If a future capability needs a secret, declare it in `.env.example` with
a comment explaining why an environment variable is the right mechanism, and never commit
the value.

## Rotation and revocation

Because nothing is stored by this system, rotation is simply: revoke on the provider, then
re-authenticate locally. There is no file to clean up and no cache to invalidate. The
helper resolves a fresh token on every connection.

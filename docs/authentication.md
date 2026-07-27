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

## Resend — OAuth (Resend-hosted remote server)

**What it is:** the **official** Resend MCP server — `github.com/resend/resend-mcp`, published to
npm as `resend-mcp` and maintained by the Resend team (the same accounts that publish the `resend`
SDK). Resend hosts it at `https://mcp.resend.com/mcp`; we connect to the hosted server rather than
running the local package.

**Why OAuth and not an API key:** the local package (`npx -y resend-mcp`) needs `RESEND_API_KEY`
present in configuration. The hosted server supports OAuth, so **no Resend key is ever written to
`~/.claude.json`, this repository, or anywhere else at rest.** That is the deciding factor; a Bearer
key is also supported upstream and is deliberately not used here.

**Where the credential lives:** Claude Code's own credential store.

**Set it up:** in Claude Code run `/mcp`, select `resend`, choose Authenticate, complete the browser
login to Resend. One time per machine. Claude Code must be restarted after `studio bootstrap` adds
the server before `/mcp` will list it.

**What it owns:** *operating and inspecting* the Resend account — domain/DNS verification status,
delivery logs, suppressions, sending a real test message. It is **not** the delivery path for site
mail: the Adamenko site sends through its own Resend REST call in `src/lib/email/`, which has no
runtime dependency on this server.

**Verify:** `studio doctor` shows `resend` as `configured, not authenticated` before the flow and
passing after it; `/mcp` shows resend connected.

## Nothing else needs a credential

Chrome DevTools, Playwright, Context7 and shadcn all run unauthenticated. The vault servers
read local files. If a future capability needs a secret, declare it in `.env.example` with
a comment explaining why an environment variable is the right mechanism, and never commit
the value.

## Rotation and revocation

Because nothing is stored by this system, rotation is simply: revoke on the provider, then
re-authenticate locally. There is no file to clean up and no cache to invalidate. The
helper resolves a fresh token on every connection.

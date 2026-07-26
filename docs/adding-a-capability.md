# Adding a capability

Adding a capability is a **data edit**, not a code edit. Both `bootstrap` and `doctor` read
`manifest/capabilities.json`, so a correct entry is installed and health-checked automatically.

## 1. Decide it earns its place

Answer these before writing anything. Most candidates should fail here.

- **What can Claude do afterwards that it cannot do now?** If the answer is vague, stop.
- **Does something already own this?** A built-in, an existing server, or an existing skill.
  Duplicate capability is context cost with no gain.
- **Is it methodology or evidence?** Skills carry method; MCP servers carry evidence and
  actions. A candidate skill that merely wraps a tool you already have is a duplicate.
- **What does it cost?** A skill's entire SKILL.md enters context on invocation. Weigh size
  against value: an 87 KB skill has to be about ten times more useful than an 8 KB one.
- **Does it conflict with the operating model?** Reject anything imposing rigid mandates
  over judgement, or inserting an orchestration layer between Claude and its tools.
- **Trust:** is there a licence? Is it maintained? What does it execute?

## 2. Add the manifest entry

MCP server:

```json
{
  "id": "example",
  "scope": "user",
  "required": false,
  "transport": "stdio",
  "command": "cmd",
  "args": ["/c", "npx", "-y", "example-mcp@latest"],
  "posixCommand": "npx",
  "posixArgs": ["-y", "example-mcp@latest"],
  "owns": "One sentence: the responsibility this server owns.",
  "auth": null,
  "health": { "kind": "mcp-connect" }
}
```

Vendored skill:

```json
{
  "id": "example-skill",
  "strategy": "vendored",
  "scope": "user",
  "required": true,
  "source": "https://raw.githubusercontent.com/owner/repo/main/SKILL.md",
  "license": "MIT",
  "vendoredAt": "YYYY-MM-DD",
  "localPath": "skills/example-skill",
  "owns": "What it judges or produces."
}
```

Use `${PYTHON}`, `${VAULT}` and `${CLAUDE_HOME}` for anything machine-specific.
**Never write an absolute path into the manifest.**

## 3. Add the routing trigger

An installed capability that nothing routes to is dead weight. This was the original
failure that motivated the whole system: seven healthy MCP servers, five of them never
invoked once in 36 sessions.

Add a row to the relevant table in `config/CLAUDE.global.md` with a **fire** condition and
a **do-not-use-for** condition. Both matter; a trigger with no boundary produces a tool
that fires on everything, which is its own kind of broken.

## 4. Vendor properly, if vendoring

Put the files under `skills/<id>/` with the upstream `LICENSE` and a `PROVENANCE.md`
recording the upstream URL, licence, date, **what you deliberately did not take**, and the
update and remove commands. `doctor` warns on a vendored skill with no provenance.

## 5. Converge and verify

```
studio bootstrap --dry-run     # read the plan
studio bootstrap
studio doctor
```

Then **actually invoke it** in a fresh session. Configuration is a claim; invocation is
evidence.

## 6. Record the decision

Add it to the vault's `00_System/capability-routing.md` classification record, including
what you rejected and why. The rejections are more valuable than the approvals: they stop
the same candidate being re-evaluated every six months.

## Removing a capability

Delete the manifest entry and the routing row, then remove the live artefact:

```
claude mcp remove --scope user <id>
claude plugin uninstall <id>@<marketplace>
rm -rf ~/.claude/skills/<id>
```

`doctor` reports anything configured but no longer in the manifest, which is how you find
leftovers.

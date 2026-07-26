# Updating

Four versions matter, and conflating them is how environments rot:

| | Meaning |
|---|---|
| **upstream** | what the source currently publishes |
| **pinned** | what `manifest/capabilities.json` declares |
| **installed** | what is actually on this machine |
| **verified** | what was last invocation-tested |

`doctor` compares installed against pinned. Neither it nor `bootstrap` silently pulls
`latest` for anything that carries judgement.

## The loop

```
check  ->  inspect  ->  update  ->  verify  ->  commit
```

Never skip **inspect**. A skill is a prompt: a bad upstream change alters how Claude thinks
and produces no error anywhere.

## By dependency type

**Marketplace plugins** — `frontend-design`, `typescript-lsp`, `pr-review-toolkit`

```
claude plugin update <name>@claude-plugins-official
```

First-party and low risk. Re-run `doctor` afterwards.

**Upstream-installer skills** — `humanizer`

```
npx skills update humanizer --global
```

Then bump `pinnedVersion` in the manifest, and read the diff if the major version moved.

**Vendored skills** — `redesign-existing-projects`

Deliberately manual. Fetch the upstream file, **diff it**, and only then accept:

```
curl -L <source-from-PROVENANCE.md> -o /tmp/SKILL.md
diff skills/redesign-existing-projects/SKILL.md /tmp/SKILL.md
```

Read the diff for rigid mandates, unwanted prescriptions, or scope creep. The reason this
one is vendored rather than referenced is precisely that upstream is a fast-moving
single-maintainer repository whose flagship skill carries exactly those problems. Update
`PROVENANCE.md` with the new date, then run `studio bootstrap`.

**npx-based MCP servers** float on `@latest` by design: they are thin protocol adapters
where the newest version is nearly always correct, and pinning them would mean editing the
manifest for every upstream patch. If one starts misbehaving, pin the exact version in the
manifest `args` and record why.

## After any update

```
studio doctor
```

Then invoke at least one thing that changed, in a fresh session. Promote it to **verified**
only after that, and commit the manifest change with the reason in the message.

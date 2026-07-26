# Provenance — redesign-existing-projects

- **Upstream:** https://github.com/Leonxlnx/taste-skill — path `skills/redesign-skill/SKILL.md`
- **License:** MIT (see `LICENSE`, Copyright (c) 2026 Leonxlnx) — vendored, attribution retained
- **Vendored:** 2026-07-26, at upstream state pushed 2026-07-23
- **Size:** 15,060 B

## Why only this one file

The upstream repository ships **13 skills**. Only this one is installed, deliberately:

- `taste-skill` (the flagship, 87,253 B) was **rejected**. It is ~10x the size of Anthropic's
  `frontend-design` (8,315 B) for heavily overlapping ground — a skill's whole SKILL.md enters
  context on invocation, so ~22k tokens per use is not proportionate. It also carries hard
  aesthetic mandates ("ZERO em-dashes anywhere. Zero.") that conflict with French typography on
  this operator's FR/EN sites, and a fixed "premium palette ban" listing specific hex families.
- The style variants (`soft-`, `minimalist-`, `brutalist-`, `stitch-`) are visual presets, which
  is the opposite of the goal: a point of view derived from the brief, not a preset picked off a
  shelf.
- The `imagegen-*` and `brandkit` skills emit prompts for external image generators. The studio
  trust model forbids fabricated visual assets: real assets and verified data only.

This file covers the gap `frontend-design` genuinely does not: **auditing and upgrading an
interface that already exists** (Scan → Diagnose → Fix, with preservation rules for navigation,
legal links, and real copy). It complements `frontend-design`; it does not replace it.

## Update / remove

```
# update (re-vendor)
curl -L https://raw.githubusercontent.com/Leonxlnx/taste-skill/main/skills/redesign-skill/SKILL.md \
  -o ~/.claude/skills/redesign-existing-projects/SKILL.md
# remove
rm -rf ~/.claude/skills/redesign-existing-projects
```

Re-read the diff before accepting an update: upstream is a fast-moving single-maintainer repo,
and a future revision could import the flagship's rigid mandates.

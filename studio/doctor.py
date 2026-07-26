"""studio doctor -- report what is healthy, what is missing, and what needs a human.

Reads the same manifest bootstrap converges to, so the two can never drift apart.
Distinguishes PASS / WARNING / FAIL / NOT CONFIGURED / AUTH REQUIRED, and only ever
exits non-zero when something *required* genuinely failed. An absent optional
capability is information, not a catastrophe.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .common import (
    AUTH_REQUIRED,
    FAIL,
    NOT_CONFIGURED,
    PASS,
    WARN,
    Report,
    build_context,
    claude_home,
    find_chrome,
    find_claude_cli,
    find_vault,
    load_manifest,
    read_claude_json,
    read_user_settings,
    resolve_vars,
    run,
)

MANAGED_BEGIN = "<!-- BEGIN AI-STUDIO MANAGED BLOCK"


def _mcp_status_table(claude_cli: Path | None, timeout: int) -> dict[str, str] | None:
    """One `claude mcp list` call, parsed into {server: state}. None if unavailable."""
    if not claude_cli:
        return None
    rc, out = run([str(claude_cli), "mcp", "list"], timeout=timeout)
    if not out:
        return None
    table: dict[str, str] = {}
    # Lines look like: "name: <command or url> - <status text>"
    for raw in out.splitlines():
        line = raw.strip()
        m = re.match(r"^([A-Za-z0-9_.\-]+):\s+(.*)$", line)
        if not m:
            continue
        name, rest = m.group(1), m.group(2)
        low = rest.lower()
        if "connected" in low:
            table[name] = "connected"
        elif "pending approval" in low:
            table[name] = "pending"
        elif "needs authentication" in low or "auth" in low:
            table[name] = "auth"
        elif "failed" in low or "error" in low:
            table[name] = "failed"
    return table or None


def _detect_prereq(spec: dict, ctx: dict) -> tuple[bool, str]:
    kind = spec.get("detect", {}).get("kind")
    if kind == "command":
        cmd = spec["detect"]["command"]
        exe = shutil.which(cmd)
        if not exe:
            return False, ""
        args = spec["detect"].get("versionArgs")
        if args:
            rc, out = run([exe] + args, timeout=25)
            first = (out.splitlines() or [""])[0].strip()
            return True, first[:60]
        return True, exe
    if kind == "claude-cli":
        cli = find_claude_cli()
        if not cli:
            return False, ""
        rc, out = run([str(cli), "--version"], timeout=30)
        return True, (out.splitlines() or [""])[0].strip()[:40]
    if kind == "python":
        import sys

        return True, f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if kind == "chrome":
        c = find_chrome()
        return (bool(c), str(c) if c else "")
    return False, "unknown detector"


def run_doctor(argv: list[str]) -> int:
    fast = "--fast" in argv
    manifest = load_manifest()
    ctx = build_context()
    rep = Report()
    section: dict[str, str] = {}

    def add(sec, name, *a, **kw):
        section[name] = sec
        return rep.add(name, *a, **kw)

    print(f"\n  {manifest['studio']['name']} - environment health\n  " + "-" * 52)

    # ---------------------------------------------------------- prerequisites
    for p in manifest["prerequisites"]:
        ok, detail = _detect_prereq(p, ctx)
        required = p.get("required", False)
        if ok:
            add("Prerequisites", p["name"], PASS, detail, required=required)
        else:
            add(
                "Prerequisites",
                p["name"],
                FAIL if required else NOT_CONFIGURED,
                "",
                p.get("install", ""),
                required,
            )

    # ---------------------------------------------------------- git behaviour
    if os.name == "nt":
        rc, lp = run(["git", "config", "--global", "--get", "core.longpaths"], timeout=20)
        if lp.strip().lower() == "true":
            add("Prerequisites", "git core.longpaths", PASS, "enabled")
        else:
            add(
                "Prerequisites",
                "git core.longpaths",
                WARN,
                "disabled",
                "restoring the vault can fail with 'Filename too long'; run: studio bootstrap",
            )

    # ---------------------------------------------------------- vault
    vault = find_vault()
    if vault:
        add("Knowledge layer", "AI-Studio vault", PASS, str(vault))
        graph = vault / "graphify-out" / "resolver" / "resolved-graph.json"
        add(
            "Knowledge layer",
            "vault resolved graph",
            PASS if graph.exists() else WARN,
            str(graph.name) if graph.exists() else "not built",
            "" if graph.exists() else "run: python tools/graph-resolver/resolver.py --full (in the vault)",
        )
    else:
        add(
            "Knowledge layer",
            "AI-Studio vault",
            NOT_CONFIGURED,
            "",
            "clone the private vault, then set STUDIO_VAULT to its path",
        )

    # ---------------------------------------------------------- MCP servers
    cfg = read_claude_json()
    configured = cfg.get("mcpServers") or {}
    claude_cli = find_claude_cli()
    live = None if fast else _mcp_status_table(claude_cli, timeout=240)

    for s in manifest["mcpServers"]:
        sid = s["id"]
        required = s.get("required", False)
        entry = configured.get(sid)
        if not entry:
            needs = s.get("requires") or []
            if "vault" in needs and not vault:
                add("MCP servers", sid, NOT_CONFIGURED, "needs the vault", "clone the vault, then: studio bootstrap")
            else:
                add("MCP servers", sid, FAIL if required else NOT_CONFIGURED, "not in ~/.claude.json",
                    "studio bootstrap", required)
            continue

        scope_note = "user scope"
        if live is None:
            add("MCP servers", sid, PASS, f"configured, {scope_note}", "run without --fast to test connectivity")
            continue

        state = live.get(sid)
        if state == "connected":
            add("MCP servers", sid, PASS, f"connected, {scope_note}")
        elif state == "auth":
            auth = s.get("auth") or {}
            add("MCP servers", sid, AUTH_REQUIRED, "configured, not authenticated",
                auth.get("operatorAction", "authenticate in /mcp"))
        elif state == "pending":
            add("MCP servers", sid, WARN, "pending approval",
                "project-scoped approval detected; this environment expects user scope")
        elif state == "failed":
            add("MCP servers", sid, FAIL if required else WARN, "failed to connect",
                (s.get("auth") or {}).get("operatorAction", ""), required)
        else:
            add("MCP servers", sid, WARN, "configured, state unknown")

    for extra in sorted(set(configured) - {s["id"] for s in manifest["mcpServers"]}):
        add("MCP servers", extra, WARN, "configured but not in manifest",
            "add it to manifest/capabilities.json or remove it")

    # ---------------------------------------------------------- plugins
    settings = read_user_settings()
    enabled = settings.get("enabledPlugins") or {}
    markets = settings.get("extraKnownMarketplaces") or {}
    for m in manifest["marketplaces"]:
        add("Plugins", f"marketplace: {m['id']}", PASS if m["id"] in markets else NOT_CONFIGURED,
            m.get("repo", ""), "studio bootstrap")
    for pl in manifest["plugins"]:
        key = f"{pl['id']}@{pl['marketplace']}"
        ok = enabled.get(key) is True
        add("Plugins", pl["id"], PASS if ok else (FAIL if pl.get("required") else NOT_CONFIGURED),
            "enabled, user scope" if ok else "not enabled", "studio bootstrap", pl.get("required", False))

    # ---------------------------------------------------------- skills
    skills_dir = claude_home() / "skills"
    for sk in manifest["skills"]:
        if sk.get("strategy") == "external":
            present = (skills_dir / sk["id"]).exists()
            add("Skills", sk["id"], PASS if present else NOT_CONFIGURED,
                "present" if present else "not installed", "installed by its own package")
            continue
        d = skills_dir / sk["id"]
        has_skill_md = (d / "SKILL.md").exists()
        if has_skill_md:
            detail = "installed"
            if sk.get("strategy") == "vendored":
                prov = (d / "PROVENANCE.md").exists()
                detail = "vendored" + ("" if prov else ", PROVENANCE.md MISSING")
                add("Skills", sk["id"], PASS if prov else WARN, detail,
                    "" if prov else "vendored skills must carry provenance", sk.get("required", False))
                continue
            add("Skills", sk["id"], PASS, detail, required=sk.get("required", False))
        else:
            add("Skills", sk["id"], FAIL if sk.get("required") else NOT_CONFIGURED, "missing",
                sk.get("install", "studio bootstrap"), sk.get("required", False))

    # ---------------------------------------------------------- routing config
    for c in manifest["config"]:
        target = Path(resolve_vars(c["target"], ctx) or "")
        if not target.exists():
            add("Routing", c["id"], FAIL if c.get("required") else NOT_CONFIGURED, "missing",
                "studio bootstrap", c.get("required", False))
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        if MANAGED_BEGIN in text:
            add("Routing", c["id"], PASS, f"managed block present ({len(text)} B)")
        else:
            add("Routing", c["id"], WARN, "present, but no managed block",
                "studio bootstrap will insert one and preserve your text")

    # ---------------------------------------------------------- GitHub auth
    helper = claude_home() / "bin" / ("github-mcp-headers.cmd" if os.name == "nt" else "github-mcp-headers.sh")
    if helper.exists():
        rc, out = run([str(helper)] if os.name == "nt" else ["sh", str(helper)], timeout=30)
        if '"Authorization"' in out:
            add("Authentication", "github credential", PASS, "resolved from OS credential store")
        else:
            add("Authentication", "github credential", AUTH_REQUIRED, "helper found no token",
                "run 'gh auth login', or push once over HTTPS so Git Credential Manager stores one")
    else:
        add("Authentication", "github credential helper", NOT_CONFIGURED, "", "studio bootstrap")

    creds = claude_home() / ".credentials.json"
    add("Authentication", "figma credential", PASS if creds.exists() else NOT_CONFIGURED,
        "Claude Code credential store" if creds.exists() else "",
        "run /mcp in Claude Code, pick figma, Authenticate")

    rep.render(section)
    code, summary = rep.summary()
    print("\n  " + "-" * 52)
    print(f"  {summary}")
    if code:
        print("  Required capabilities are failing. Run: studio bootstrap")
    print()
    return code

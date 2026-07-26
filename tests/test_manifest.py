"""Deterministic checks on the manifest and the machine-independence rules.

Runs with plain `python tests/test_manifest.py` (no pytest required), and is also
importable by pytest if you have it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio.common import build_context, load_manifest, resolve_vars  # noqa: E402

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        FAILURES.append(msg)


def test_manifest_parses() -> dict:
    m = load_manifest()
    check(m.get("schemaVersion") == 1, "manifest declares schemaVersion 1")
    for key in ("prerequisites", "mcpServers", "plugins", "skills", "config", "ownership"):
        check(key in m, f"manifest has '{key}'")
    return m


def test_ids_unique(m: dict) -> None:
    for section in ("prerequisites", "mcpServers", "plugins", "skills"):
        ids = [x["id"] for x in m[section]]
        check(len(ids) == len(set(ids)), f"{section}: ids are unique")


def test_every_capability_declares_ownership(m: dict) -> None:
    for s in m["mcpServers"]:
        check(bool(s.get("owns")), f"mcp '{s['id']}' declares what it owns")
    for p in m["plugins"]:
        check(bool(p.get("owns")), f"plugin '{p['id']}' declares what it owns")
    for s in m["skills"]:
        check(bool(s.get("owns")), f"skill '{s['id']}' declares what it owns")


def test_no_absolute_paths(m: dict) -> None:
    """Machine paths must never be baked into the manifest."""
    raw = json.dumps(m)
    windows_abs = re.findall(r'"[A-Za-z]:[\\/][^"]*"', raw)
    posix_abs = re.findall(r'"/(?:home|Users)/[^"]*"', raw)
    check(not windows_abs, f"no Windows absolute paths (found {windows_abs[:3]})")
    check(not posix_abs, f"no POSIX home paths (found {posix_abs[:3]})")


def test_no_secrets(m: dict) -> None:
    raw = json.dumps(m)
    patterns = [r"gh[pousr]_[A-Za-z0-9]{20,}", r"sk-[A-Za-z0-9]{20,}", r"AIza[A-Za-z0-9_\-]{30,}"]
    hits = [p for p in patterns if re.search(p, raw)]
    check(not hits, "manifest contains no credential-shaped strings")
    for s in m["mcpServers"]:
        headers = s.get("headers") or {}
        check(not headers, f"mcp '{s['id']}' declares no static headers (use headersHelper)")


def test_vendored_skills_have_provenance(m: dict) -> None:
    for s in m["skills"]:
        if s.get("strategy") != "vendored":
            continue
        d = ROOT / s["localPath"]
        check((d / "SKILL.md").exists(), f"vendored '{s['id']}': SKILL.md present")
        check((d / "PROVENANCE.md").exists(), f"vendored '{s['id']}': PROVENANCE.md present")
        check((d / "LICENSE").exists(), f"vendored '{s['id']}': LICENSE present")
        check(bool(s.get("license")), f"vendored '{s['id']}': licence declared in manifest")


def test_config_sources_exist(m: dict) -> None:
    for c in m["config"]:
        check((ROOT / c["source"]).exists(), f"config source '{c['source']}' exists")


def test_variables_resolve(m: dict) -> None:
    ctx = build_context()
    for s in m["mcpServers"]:
        for key in ("command", "args"):
            if key not in s:
                continue
            needs_vault = "vault" in (s.get("requires") or [])
            if needs_vault and "VAULT" not in ctx:
                continue
            check(resolve_vars(s[key], ctx) is not None, f"mcp '{s['id']}'.{key} resolves")


def test_auth_declares_operator_action(m: dict) -> None:
    for s in m["mcpServers"]:
        auth = s.get("auth")
        if auth:
            check(bool(auth.get("operatorAction")), f"mcp '{s['id']}': auth names an operator action")
            check(bool(auth.get("storedBy")), f"mcp '{s['id']}': auth says where the credential lives")


def main() -> int:
    print("\n  manifest tests\n  " + "-" * 40)
    m = test_manifest_parses()
    test_ids_unique(m)
    test_every_capability_declares_ownership(m)
    test_no_absolute_paths(m)
    test_no_secrets(m)
    test_vendored_skills_have_provenance(m)
    test_config_sources_exist(m)
    test_variables_resolve(m)
    test_auth_declares_operator_action(m)
    print("  " + "-" * 40)
    if FAILURES:
        print(f"  {len(FAILURES)} failure(s)\n")
        return 1
    print("  all checks passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

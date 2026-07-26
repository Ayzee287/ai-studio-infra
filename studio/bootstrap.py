"""studio bootstrap -- converge this machine onto the manifest.

Safety contract:
  * idempotent      re-running changes nothing once converged
  * never silent    every action is printed; --dry-run prints only
  * never clobber   any file we modify is copied to ~/.claude/backups/<timestamp>/ first
  * never merge blindly into prose: the global CLAUDE.md is edited as a delimited
    managed block, so operator-authored text around it survives verbatim
  * never write a credential anywhere
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .common import (
    REPO_ROOT,
    backup_file,
    build_context,
    claude_home,
    claude_json,
    find_claude_cli,
    find_git_bash,
    find_vault,
    load_manifest,
    read_claude_json,
    resolve_vars,
    run,
)

MANAGED_BEGIN = "<!-- BEGIN AI-STUDIO MANAGED BLOCK v1 -- maintained by `studio bootstrap`; text outside this block is preserved -->"
MANAGED_END = "<!-- END AI-STUDIO MANAGED BLOCK -->"


class Runner:
    def __init__(self, dry: bool, tag: str):
        self.dry = dry
        self.tag = tag
        self.changed = 0
        self.skipped = 0

    def act(self, msg: str) -> bool:
        if self.dry:
            print(f"    WOULD  {msg}")
            return False
        print(f"    DO     {msg}")
        self.changed += 1
        return True

    def ok(self, msg: str) -> None:
        print(f"    OK     {msg}")
        self.skipped += 1

    def warn(self, msg: str) -> None:
        print(f"    WARN   {msg}")


def _write_json(path: Path, data: dict, r: Runner) -> None:
    backup_file(path, r.tag)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def _norm_path(value: str) -> str:
    """Compare paths by meaning, not by spelling.

    A converged machine must report zero changes, so cosmetic differences must not read as
    drift: `C:/x` vs `C:\\x`, and case on Windows, are the same path.
    """
    if not isinstance(value, str):
        return value
    looks_like_path = ("/" in value or "\\" in value) and not value.startswith(("http://", "https://"))
    if not looks_like_path:
        return value
    out = value.replace("\\", "/")
    if os.name == "nt":
        out = out.lower()
    return out


def _norm_entry(entry: dict) -> dict:
    """Normalise an MCP entry for comparison only (never for writing)."""
    if not isinstance(entry, dict):
        return {}
    out = {}
    for k, v in entry.items():
        # An absent `env` and an empty `env` mean the same thing.
        if k == "env" and not v:
            continue
        if isinstance(v, str):
            out[k] = _norm_path(v)
        elif isinstance(v, list):
            out[k] = [_norm_path(i) if isinstance(i, str) else i for i in v]
        else:
            out[k] = v
    return out


def _sync_mcp(manifest: dict, ctx: dict, r: Runner) -> None:
    print("\n  MCP servers")
    cfg = read_claude_json()
    servers = cfg.setdefault("mcpServers", {})
    vault = find_vault()
    dirty = False

    for spec in manifest["mcpServers"]:
        sid = spec["id"]
        needs = spec.get("requires") or []
        if "vault" in needs and not vault:
            r.warn(f"{sid}: skipped, vault not present (set STUDIO_VAULT)")
            continue

        if spec["transport"] == "stdio":
            cmd_key, args_key = ("command", "args")
            if os.name != "nt" and spec.get("posixCommand"):
                cmd_key, args_key = ("posixCommand", "posixArgs")
            command = resolve_vars(spec[cmd_key], ctx)
            args = resolve_vars(spec[args_key], ctx)
            if command is None or args is None:
                r.warn(f"{sid}: skipped, unresolved variable")
                continue
            desired = {"type": "stdio", "command": command, "args": args}
        else:
            desired = {"type": spec["transport"], "url": spec["url"]}
            helper_key = "headersHelper" if os.name == "nt" else "posixHeadersHelper"
            if spec.get(helper_key):
                h = resolve_vars(spec[helper_key], ctx)
                if h:
                    desired["headersHelper"] = os.path.normpath(h) if os.name == "nt" else h

        current = servers.get(sid)
        if current is not None and _norm_entry(current) == _norm_entry(desired):
            r.ok(f"{sid}: already correct")
            continue
        if current is None:
            if r.act(f"{sid}: add at user scope"):
                servers[sid] = desired
                dirty = True
        else:
            if r.act(f"{sid}: update user-scope definition (previous value backed up)"):
                # Preserve operator-added keys we do not manage (timeout, alwaysLoad, ...).
                merged = dict(current)
                merged.update(desired)
                servers[sid] = merged
                dirty = True

    if dirty and not r.dry:
        _write_json(claude_json(), cfg, r)


def _shell_cmd(cmd: str) -> list[str]:
    """Wrap a manifest-declared install command for the platform shell."""
    if os.name == "nt":
        return ["cmd", "/c", cmd]
    return ["sh", "-lc", cmd]


def _to_posix_path(p: Path) -> str:
    r"""C:\Users\me\x.sh -> /c/Users/me/x.sh  (the form Git Bash expects)."""
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


def _sync_github_helper(r: Runner) -> None:
    print("\n  GitHub credential helper")
    bindir = claude_home() / "bin"
    src_sh = REPO_ROOT / "config" / "github-mcp-headers.sh"
    dst_sh = bindir / "github-mcp-headers.sh"
    dst_cmd = bindir / "github-mcp-headers.cmd"

    if not src_sh.exists():
        r.warn("template config/github-mcp-headers.sh missing from the repository")
        return

    if dst_sh.exists() and dst_sh.read_text(encoding="utf-8") == src_sh.read_text(encoding="utf-8"):
        r.ok("headers helper script up to date")
    else:
        if r.act(f"install headers helper -> {dst_sh}"):
            bindir.mkdir(parents=True, exist_ok=True)
            backup_file(dst_sh, r.tag)
            shutil.copy2(src_sh, dst_sh)

    if os.name == "nt":
        bash = find_git_bash()
        if not bash:
            r.warn("git bash not found; the Windows wrapper needs it")
            return
        content = f'@echo off\r\n"{bash}" -c "{_to_posix_path(dst_sh)}"\r\n'
        # Compare with newlines normalised: read_text() collapses CRLF to LF, so a naive
        # equality check would report a change on every run and break idempotency.
        existing_cmd = (
            dst_cmd.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
            if dst_cmd.exists()
            else None
        )
        if existing_cmd is not None and existing_cmd == content.replace("\r\n", "\n"):
            r.ok("headers helper wrapper up to date")
        else:
            if r.act(f"write wrapper -> {dst_cmd}"):
                bindir.mkdir(parents=True, exist_ok=True)
                backup_file(dst_cmd, r.tag)
                # newline="" disables translation: without it Python rewrites the \n inside
                # our explicit \r\n, producing \r\r\n and a file that never compares equal.
                dst_cmd.write_text(content, encoding="ascii", newline="")


def _sync_git_longpaths(r: Runner) -> None:
    """Ensure Windows git can check out long paths.

    Found by an actual recovery test, not by reading docs: cloning the knowledge vault
    failed with 'Filename too long' because Windows' MAX_PATH is 260 characters and git
    defaults core.longpaths to false. The vault legitimately contains 111-character paths
    (dated note titles, plus an archived object store) and will only grow, so any clone
    into a moderately deep directory silently loses files. A backup that cannot be
    restored is not a backup, so this belongs in bootstrap rather than in a README.
    """
    if os.name != "nt":
        return
    print("\n  Git configuration")
    rc, out = run(["git", "config", "--global", "--get", "core.longpaths"], timeout=20)
    if out.strip().lower() == "true":
        r.ok("core.longpaths: already enabled")
        return
    if r.act("core.longpaths: enable globally (required to clone deep repos on Windows)"):
        rc2, out2 = run(["git", "config", "--global", "core.longpaths", "true"], timeout=20)
        if rc2 != 0:
            r.warn(f"  could not set core.longpaths: {out2[:120]}")


def _sync_plugins(manifest: dict, r: Runner) -> None:
    print("\n  Marketplaces and plugins")
    cli = find_claude_cli()
    if not cli:
        required = [p["id"] for p in manifest["plugins"] if p.get("required")]
        r.warn("Claude Code CLI not found -- plugins cannot be installed")
        if required:
            r.warn(f"  {len(required)} REQUIRED plugin(s) skipped: {', '.join(required)}")
        r.warn("  install Claude Code, or set STUDIO_CLAUDE_CLI to its binary, then re-run")
        return

    rc, out = run([str(cli), "plugin", "marketplace", "list"], timeout=180)
    for m in manifest["marketplaces"]:
        if m["id"] in out:
            r.ok(f"marketplace {m['id']}: present")
        elif r.act(f"marketplace {m['id']}: add {m['repo']}"):
            rc2, out2 = run([str(cli), "plugin", "marketplace", "add", m["repo"]], timeout=300)
            if rc2 != 0:
                r.warn(f"  add failed: {out2[:160]}")

    rc, installed = run([str(cli), "plugin", "list"], timeout=180)
    for pl in manifest["plugins"]:
        key = f"{pl['id']}@{pl['marketplace']}"
        if pl["id"] in installed:
            r.ok(f"plugin {pl['id']}: installed")
        elif r.act(f"plugin {pl['id']}: install at user scope"):
            rc2, out2 = run([str(cli), "plugin", "install", "--scope", "user", key], timeout=420)
            if rc2 != 0:
                r.warn(f"  install failed: {out2[:160]}")


def _sync_skills(manifest: dict, r: Runner) -> None:
    print("\n  Skills")
    skills_dir = claude_home() / "skills"
    for sk in manifest["skills"]:
        sid = sk["id"]
        strategy = sk.get("strategy")
        dst = skills_dir / sid

        if strategy == "external":
            r.ok(f"{sid}: managed by its own package") if dst.exists() else r.warn(
                f"{sid}: not installed (optional; installed by its own package)"
            )
            continue

        if strategy == "vendored":
            src = REPO_ROOT / sk["localPath"]
            if not src.is_dir():
                r.warn(f"{sid}: vendored source missing at {sk['localPath']}")
                continue
            if dst.exists() and (dst / "SKILL.md").exists():
                same = (dst / "SKILL.md").read_bytes() == (src / "SKILL.md").read_bytes()
                if same:
                    r.ok(f"{sid}: up to date (vendored)")
                    continue
                if r.act(f"{sid}: update vendored copy (existing backed up)"):
                    backup_file(dst / "SKILL.md", r.tag)
                    shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                if r.act(f"{sid}: install vendored copy -> {dst}"):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(src, dst, dirs_exist_ok=True)
            continue

        if strategy == "upstream-installer":
            if dst.exists():
                r.ok(f"{sid}: present (upstream installer)")
                continue
            cmd = sk.get("install")
            if not cmd:
                r.warn(f"{sid}: missing and no install command declared")
                continue
            # Run the installer rather than printing it. A step that is universally
            # required on every clean machine is bootstrap's job, not a README line the
            # operator has to remember during a recovery.
            if r.act(f"{sid}: install via upstream installer ({cmd})"):
                rc, out = run(_shell_cmd(cmd), timeout=600)
                if rc != 0 or not dst.exists():
                    r.warn(f"  install failed (rc={rc}): {out[-200:] if out else 'no output'}")
                    r.warn(f"  run manually: {cmd}")


def _sync_config(manifest: dict, ctx: dict, r: Runner) -> None:
    print("\n  Routing configuration")
    for c in manifest["config"]:
        target = Path(resolve_vars(c["target"], ctx) or "")
        src = REPO_ROOT / c["source"]
        if not src.exists():
            r.warn(f"{c['id']}: template {c['source']} missing")
            continue
        block = MANAGED_BEGIN + "\n\n" + src.read_text(encoding="utf-8").strip() + "\n\n" + MANAGED_END

        existing = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        if MANAGED_BEGIN in existing and MANAGED_END in existing:
            start = existing.index(MANAGED_BEGIN)
            end = existing.index(MANAGED_END) + len(MANAGED_END)
            if existing[start:end].strip() == block.strip():
                r.ok(f"{c['id']}: managed block up to date")
                continue
            if r.act(f"{c['id']}: refresh managed block (surrounding text preserved, file backed up)"):
                backup_file(target, r.tag)
                target.write_text(existing[:start] + block + existing[end:], encoding="utf-8")
        else:
            if r.act(f"{c['id']}: insert managed block at top (existing content preserved below)"):
                target.parent.mkdir(parents=True, exist_ok=True)
                backup_file(target, r.tag)
                joined = block + ("\n\n" + existing.lstrip() if existing.strip() else "\n")
                target.write_text(joined, encoding="utf-8")


def run_bootstrap(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    manifest = load_manifest()
    ctx = build_context()
    tag = time.strftime("bootstrap-%Y%m%d-%H%M%S")
    r = Runner(dry, tag)

    print(f"\n  {manifest['studio']['name']} - bootstrap{' (dry run)' if dry else ''}")
    print("  " + "-" * 52)
    print(f"    python  {ctx['PYTHON']}")
    print(f"    vault   {ctx.get('VAULT', '(not found -- set STUDIO_VAULT)')}")
    print(f"    backups {claude_home() / 'backups' / tag}")

    _sync_git_longpaths(r)
    _sync_mcp(manifest, ctx, r)
    _sync_github_helper(r)
    _sync_plugins(manifest, r)
    _sync_skills(manifest, r)
    _sync_config(manifest, ctx, r)

    print("\n  " + "-" * 52)
    if dry:
        print("  dry run: nothing was written.")
    else:
        print(f"  {r.changed} change(s), {r.skipped} already correct.")
        if r.changed:
            print("  Restart Claude Code so it picks up MCP/plugin changes, then: studio doctor")
        else:
            print("  Environment already matches the manifest.")
    print()
    return 0

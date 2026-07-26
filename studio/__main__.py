"""AI Studio infrastructure CLI.

    studio doctor      report environment health
    studio bootstrap   converge this machine onto manifest/capabilities.json
    studio onboard     add a project to the system
    studio manifest    print the resolved manifest
"""

from __future__ import annotations

import sys

USAGE = """
  studio <command> [options]

    doctor              Report environment health.
        --fast          Skip live MCP connectivity probing (much quicker).

    bootstrap           Converge this machine onto the manifest. Idempotent.
        --dry-run       Print planned actions without writing anything.

    onboard [PATH]      Prepare a project directory to join the system.
        --force         Overwrite an existing project CLAUDE.md.

    manifest            Print the manifest with machine variables resolved.

  Environment:
    STUDIO_VAULT        Path to the private AI-Studio knowledge vault.
    CLAUDE_CONFIG_DIR   Override for ~/.claude.
"""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    cmd, rest = argv[0], argv[1:]

    if cmd == "doctor":
        from .doctor import run_doctor

        return run_doctor(rest)
    if cmd == "bootstrap":
        from .bootstrap import run_bootstrap

        return run_bootstrap(rest)
    if cmd == "onboard":
        from .onboard import run_onboard

        return run_onboard(rest)
    if cmd == "manifest":
        import json

        from .common import build_context, load_manifest, resolve_vars

        m = load_manifest()
        ctx = build_context()
        for s in m.get("mcpServers", []):
            for k in ("command", "args", "headersHelper", "posixHeadersHelper"):
                if k in s:
                    s[k] = resolve_vars(s[k], ctx) or s[k]
        print(json.dumps({"context": ctx, "manifest": m}, indent=2))
        return 0

    print(f"unknown command: {cmd}")
    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

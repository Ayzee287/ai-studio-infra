"""studio onboard -- add a project to the system.

The whole point: a project inherits every global capability automatically, because
MCP servers, plugins and skills all live at user scope. Onboarding therefore writes
*no* infrastructure config. It only seeds a project CLAUDE.md for facts that are
genuinely local to that project.

If you ever find yourself adding a .mcp.json here, stop: that is the failure mode
this architecture exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

from .common import REPO_ROOT, backup_file


def run_onboard(argv: list[str]) -> int:
    force = "--force" in argv
    positional = [a for a in argv if not a.startswith("-")]
    target = Path(positional[0]).resolve() if positional else Path.cwd()

    if not target.is_dir():
        print(f"  not a directory: {target}")
        return 2

    print(f"\n  Onboarding: {target}")
    print("  " + "-" * 52)

    template = REPO_ROOT / "templates" / "project" / "CLAUDE.md"
    dest = target / "CLAUDE.md"

    if dest.exists() and not force:
        print(f"    OK     CLAUDE.md already exists -- left untouched (use --force to replace)")
    else:
        if dest.exists():
            backup_file(dest, "onboard")
            print("    DO     existing CLAUDE.md backed up")
        dest.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"    DO     wrote {dest.name} from template")

    stray = target / ".mcp.json"
    if stray.exists():
        print("    WARN   .mcp.json found in this project.")
        print("           This environment keeps every MCP server at user scope; a project-scoped")
        print("           .mcp.json reintroduces trust/approval coupling. Remove it unless the")
        print("           server genuinely only makes sense inside this one repository.")

    print("\n    Inherited automatically (nothing to configure):")
    print("      MCP servers, plugins, skills, and capability routing -- all user scope.")
    print("\n    Add to the project CLAUDE.md only what is TRUE ABOUT THIS PROJECT:")
    print("      stack, commands, conventions, constraints, business facts.")
    print()
    return 0

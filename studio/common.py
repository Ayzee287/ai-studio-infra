"""Shared plumbing: paths, manifest loading, variable resolution, reporting.

Design rule: nothing machine-specific is ever written into the manifest or into this
repository. Every absolute path is resolved here, at runtime, from the actual machine.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"

# ---------------------------------------------------------------- status levels

PASS = "PASS"
WARN = "WARNING"
FAIL = "FAIL"
NOT_CONFIGURED = "NOT CONFIGURED"
AUTH_REQUIRED = "AUTH REQUIRED"

# Exit-code policy: only a genuine failure of something *required* is non-zero.
# An optional capability that is absent is information, not an error.
_EXIT_WORTHY = {FAIL}

_COLORS = {
    PASS: "\033[32m",
    WARN: "\033[33m",
    FAIL: "\033[31m",
    NOT_CONFIGURED: "\033[90m",
    AUTH_REQUIRED: "\033[36m",
}
_RESET = "\033[0m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name == "nt" and not os.environ.get("WT_SESSION") and not os.environ.get("TERM"):
        # Legacy conhost may not handle ANSI; be conservative.
        return os.environ.get("ANSICON") is not None
    return True


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""
    hint: str = ""
    required: bool = False

    @property
    def is_blocking(self) -> bool:
        return self.status in _EXIT_WORTHY and self.required


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, *a, **kw) -> Result:
        r = Result(*a, **kw)
        self.results.append(r)
        return r

    def render(self, section_of: dict[str, str] | None = None) -> None:
        color = _supports_color()
        width = max((len(r.name) for r in self.results), default=10)
        current_section = None
        for r in self.results:
            sec = (section_of or {}).get(r.name)
            if sec and sec != current_section:
                current_section = sec
                print(f"\n  {sec}")
            tag = r.status
            if color:
                tag = f"{_COLORS.get(r.status, '')}{r.status}{_RESET}"
            pad = " " * (len(r.status.ljust(15)) - len(r.status))
            line = f"    {tag}{pad}  {r.name.ljust(width)}"
            if r.detail:
                line += f"  {r.detail}"
            print(line)
            if r.hint and r.status in (FAIL, AUTH_REQUIRED, NOT_CONFIGURED, WARN):
                print(f"    {' ' * 15}  {' ' * width}  -> {r.hint}")

    def summary(self) -> tuple[int, str]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        parts = [f"{v} {k.lower()}" for k, v in counts.items()]
        blocking = [r for r in self.results if r.is_blocking]
        return (1 if blocking else 0), ", ".join(parts)


# ---------------------------------------------------------------- environment


def claude_home() -> Path:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".claude"


def claude_json() -> Path:
    return Path.home() / ".claude.json"


def find_claude_cli() -> Path | None:
    """Claude Code may be a PATH binary or bundled inside the VS Code extension."""
    which = shutil.which("claude")
    if which:
        return Path(which)
    ext_roots = [
        Path.home() / ".vscode" / "extensions",
        Path.home() / ".vscode-insiders" / "extensions",
        Path.home() / ".vscode-server" / "extensions",
    ]
    candidates: list[Path] = []
    for root in ext_roots:
        if not root.is_dir():
            continue
        for d in root.glob("anthropic.claude-code-*"):
            for rel in ("resources/native-binary/claude.exe", "resources/native-binary/claude"):
                p = d / rel
                if p.exists():
                    candidates.append(p)
    if not candidates:
        return None
    # Highest version wins; directory names sort acceptably for this purpose.
    return sorted(candidates, key=lambda p: p.parent.parent.parent.name)[-1]


def find_git_bash() -> Path | None:
    """Locate Git Bash.

    Deliberately not a single derivation. `shutil.which("git")` gives a different answer
    depending on which shell we are called from -- `D:\\Git\\cmd\\git.exe` from PowerShell
    but `/usr/bin/git` from inside Git Bash itself, where the parent-directory trick fails.
    Git is also frequently not under Program Files. So: try several roots, verify by
    existence, and never assume a drive.
    """
    if os.name != "nt":
        b = shutil.which("bash")
        return Path(b) if b else None

    roots: list[Path] = []

    git = shutil.which("git")
    if git:
        p = Path(git).resolve()
        # <root>/cmd/git.exe, <root>/bin/git.exe, <root>/mingw64/bin/git.exe
        for up in (2, 3):
            if len(p.parents) > up:
                roots.append(p.parents[up - 1])

    for env_key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env_key)
        if base:
            roots.append(Path(base) / "Git")
    for drive in ("C:", "D:", "E:"):
        roots.append(Path(drive + "\\Git"))
        roots.append(Path(drive + "\\Program Files\\Git"))

    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        for rel in ("bin/bash.exe", "usr/bin/bash.exe"):
            cand = root / rel
            if cand.exists():
                return cand
    return None


def find_vault() -> Path | None:
    """The AI-Studio knowledge vault. Explicit env var wins; otherwise look nearby."""
    env = os.environ.get("STUDIO_VAULT")
    if env and Path(env).is_dir():
        return Path(env)
    for cand in (REPO_ROOT.parent / "AI-Studio", Path.home() / "Documents" / "Workspace" / "AI-Studio"):
        if (cand / "00_System").is_dir():
            return cand
    return None


def find_chrome() -> Path | None:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    lad = os.environ.get("LOCALAPPDATA", "")
    for c in (
        Path(pf) / "Google/Chrome/Application/chrome.exe",
        Path(pf86) / "Google/Chrome/Application/chrome.exe",
        Path(lad) / "Google/Chrome/Application/chrome.exe" if lad else None,
        Path("/usr/bin/google-chrome"),
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ):
        if c and c.exists():
            return c
    return None


def resolve_vars(value, ctx: dict[str, str]):
    """Substitute ${NAME} placeholders. Returns None if a required var is missing."""
    if isinstance(value, list):
        out = []
        for v in value:
            r = resolve_vars(v, ctx)
            if r is None:
                return None
            out.append(r)
        return out
    if not isinstance(value, str):
        return value
    out = value
    for k, v in ctx.items():
        out = out.replace("${%s}" % k, str(v))
    if "${" in out:
        return None
    return out


def build_context() -> dict[str, str]:
    ctx = {
        "PYTHON": sys.executable,
        "CLAUDE_HOME": str(claude_home()),
        "HOME": str(Path.home()),
        "REPO": str(REPO_ROOT),
    }
    vault = find_vault()
    if vault:
        ctx["VAULT"] = str(vault).replace("\\", "/")
    return ctx


# ---------------------------------------------------------------- manifest


def load_manifest(path: Path | None = None) -> dict:
    p = path or MANIFEST_PATH
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def read_claude_json() -> dict:
    p = claude_json()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_user_settings() -> dict:
    p = claude_home() / "settings.json"
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------- process


def run(cmd: list[str], timeout: int = 30, cwd: Path | None = None) -> tuple[int, str]:
    """Run a command, never raise, return (rc, combined output)."""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except Exception as e:  # pragma: no cover - defensive
        return 1, str(e)


def backup_file(path: Path, tag: str) -> Path | None:
    """Copy a file into ~/.claude/backups/<tag>/ before it is modified."""
    if not path.exists():
        return None
    dest_dir = claude_home() / "backups" / tag
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    n = 1
    while dest.exists():
        dest = dest_dir / f"{path.name}.{n}"
        n += 1
    shutil.copy2(path, dest)
    return dest

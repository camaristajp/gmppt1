"""
inventory.py  --  list every file in the project, with size and line count.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\inventory.py
                      Repo root, beside the gmppt/ package.

RUN FROM THE REPO ROOT:
    python inventory.py

Prints a tree of the project and a summary table. Nothing is written or
modified. Paste the output back so the handoff document's file listing can be
verified against what is actually on disk rather than reconstructed from
memory of what was delivered.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent

SKIP_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", ".venv", "venv",
             ".pytest_cache", ".mypy_cache", "node_modules"}

# Extensions counted as source, so line counts mean something.
SOURCE = {".py", ".md", ".json", ".txt", ".cfg", ".toml", ".yml", ".yaml"}


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def lines(p: Path) -> str:
    if p.suffix.lower() not in SOURCE:
        return ""
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            return f"{sum(1 for _ in fh):>6}"
    except Exception:
        return ""


def walk(d: Path, depth: int = 0) -> tuple[int, int]:
    """Print one directory. Returns (file count, total bytes)."""
    n_files, n_bytes = 0, 0
    try:
        entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return 0, 0

    for p in entries:
        if p.is_dir():
            if p.name in SKIP_DIRS or p.name.startswith("."):
                continue
            print(f"{'  ' * depth}{p.name}/")
            f, b = walk(p, depth + 1)
            n_files += f
            n_bytes += b
        else:
            if p.name.startswith("."):
                continue
            size = p.stat().st_size
            n_files += 1
            n_bytes += size
            print(f"{'  ' * depth}  {p.name:<44} {human(size):>10} "
                  f"{lines(p):>7}")
    return n_files, n_bytes


def main() -> int:
    print(f"PROJECT INVENTORY  --  {ROOT}")
    print("=" * 78)
    print(f"{'':>0}{'file':<46} {'size':>10} {'lines':>7}")
    print("-" * 78)

    total_files, total_bytes = walk(ROOT)

    print("-" * 78)
    print(f"{total_files} files, {human(total_bytes)} total "
          f"(hidden files, .git, __pycache__ and virtualenvs excluded)")

    # -- summary by extension ------------------------------------------------
    counts: dict[str, list[int]] = {}
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.name.startswith("."):
            continue
        if any(part in SKIP_DIRS or part.startswith(".")
               for part in p.relative_to(ROOT).parts[:-1]):
            continue
        ext = p.suffix.lower() or "(none)"
        c = counts.setdefault(ext, [0, 0])
        c[0] += 1
        c[1] += p.stat().st_size

    print(f"\nBY TYPE")
    print(f"   {'ext':<10} {'files':>7} {'size':>12}")
    print("   " + "-" * 31)
    for ext, (n, b) in sorted(counts.items(), key=lambda kv: -kv[1][1]):
        print(f"   {ext:<10} {n:>7} {human(b):>12}")

    # -- python modules, so the handoff listing can be checked ---------------
    print(f"\nPYTHON MODULES")
    for p in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        rel = p.relative_to(ROOT).as_posix()
        print(f"   {rel}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
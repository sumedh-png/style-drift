#!/usr/bin/env python3
"""
snapshot.py — capture a structured style-drift state to JSON.

Mirrors the deviation checks in scan.sh, but emits a stable JSON shape
suitable for diffing two states over time (BEFORE / AFTER fix application).

Usage:
  snapshot.py [<root>] [--toolkit <toolkit.json>] [--out <snapshot.json>]

If --out is omitted, JSON is written to stdout.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# ─── Layout detection (matches scan.sh) ──────────────────────────────────────
def detect_layout(root: Path):
    if (root / "frontend/src/components").is_dir():
        return "vite (frontend/src)", [root / "frontend/src"], [root / "frontend/src/pages"]
    if (root / "src/components").is_dir():
        return "vite (src)", [root / "src"], [root / "src/pages"]
    if (root / "app").is_dir() and (root / "components").is_dir():
        return "next.js app router", [root / "app", root / "components"], [root / "app"]
    if (root / "pages").is_dir() and (root / "components").is_dir():
        return "next.js pages router", [root / "pages", root / "components"], [root / "pages"]
    return None, [], []


# ─── grep helpers ───────────────────────────────────────────────────────────
def _existing(dirs: list[Path]) -> list[str]:
    return [str(d) for d in dirs if d.is_dir()]


def grep_files(pattern: str, dirs: list[Path]) -> list[str]:
    """Return list of files in dirs matching pattern (one entry per file)."""
    paths = _existing(dirs)
    if not paths:
        return []
    try:
        r = subprocess.run(
            ["grep", "-rEl", "--include=*.tsx", pattern, *paths],
            capture_output=True, text=True, check=False,
        )
        return sorted(line for line in r.stdout.splitlines() if line)
    except FileNotFoundError:
        return []


def grep_hits_per_file(pattern: str, dirs: list[Path]) -> dict[str, int]:
    """Return {file: count} for files matching pattern."""
    paths = _existing(dirs)
    if not paths:
        return {}
    try:
        r = subprocess.run(
            ["grep", "-rEc", "--include=*.tsx", pattern, *paths],
            capture_output=True, text=True, check=False,
        )
        out = {}
        for line in r.stdout.splitlines():
            parts = line.rsplit(":", 1)
            if len(parts) == 2 and parts[1].isdigit():
                n = int(parts[1])
                if n > 0:
                    out[parts[0]] = n
        return out
    except FileNotFoundError:
        return {}


def total_hits(per_file: dict[str, int]) -> int:
    return sum(per_file.values())


def file_list_from(per_file: dict[str, int], root: Path) -> list[str]:
    """Strip root prefix from paths so snapshots are root-portable."""
    rs = str(root) + "/"
    return sorted([p.replace(rs, "") for p in per_file.keys()])


# ─── Toolkit JSON helpers ───────────────────────────────────────────────────
def load_toolkit(path: Optional[Path]) -> Optional[dict]:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def toolkit_primitives(spec: dict) -> list[str]:
    """Names of components in any section whose title contains 'primitive'."""
    out = []
    for section in spec.get("sections", []):
        if "primitive" in (section.get("title") or "").lower():
            out.extend(c.get("name", "") for c in section.get("components", []))
    return [n for n in out if n]


def primitive_adoption(primitives: list[str], dirs: list[Path], root: Path) -> dict[str, int]:
    """Count files importing each primitive from @/components/ui/<kebab>."""
    out = {}
    for name in primitives:
        kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
        # Match either single or double quotes around the path
        pattern = r"from\s+[\"']@/components/ui/" + re.escape(kebab) + r"[\"']"
        files = grep_files(pattern, dirs)
        out[name] = len(files)
    return out


# ─── Snapshot composer ──────────────────────────────────────────────────────
GRAY_PATTERN = r"(text|bg|border|divide|ring|hover:bg|hover:text|hover:border|focus:border|focus:ring)-gray-[0-9]"
ZINC_PATTERN = r"(text|bg|border)-zinc-"
CHIP_PATTERN = r"<Badge[^>]*className=\"[^\"]*bg-(red|emerald|amber|blue|purple|green|yellow|orange)-(50|100)"
ANIMATE_PULSE_INLINE = r"className=\"[^\"]*bg-muted[^\"]*animate-pulse"
H1_PATTERN  = r"<h1[^>]*>"
CONSOLE_PATTERN = r"console\.(log|warn)\b"


def collect(root: Path, toolkit_path: Optional[Path]) -> dict:
    layout, scan_dirs, pages_dirs = detect_layout(root)
    if layout is None:
        return {"error": f"Unsupported layout at {root}"}

    toolkit = load_toolkit(toolkit_path)

    def dev(pattern, dirs):
        per = grep_hits_per_file(pattern, dirs)
        return {
            "files":      file_list_from(per, root),
            "file_count": len(per),
            "total_hits": total_hits(per),
        }

    state = {
        "timestamp":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root":           str(root),
        "layout":         layout,
        "scan_dirs":      [str(d.relative_to(root)) if d.is_relative_to(root) else str(d) for d in scan_dirs],
        "pages_dirs":     [str(d.relative_to(root)) if d.is_relative_to(root) else str(d) for d in pages_dirs],
        "toolkit": {
            "title":           toolkit.get("title") if toolkit else None,
            "version":         toolkit.get("version") if toolkit else None,
            "primitive_count": len(toolkit_primitives(toolkit)) if toolkit else None,
            "token_count":     sum(len(v) for v in (toolkit.get("tokens") or {}).values() if isinstance(v, list)) if toolkit else None,
        } if toolkit else None,
        "deviations": {
            "gray_palette":          dev(GRAY_PATTERN, scan_dirs),
            "zinc_in_pages":         dev(ZINC_PATTERN, pages_dirs),
            "chip_overrides":        dev(CHIP_PATTERN, scan_dirs),
            "animate_pulse_inline":  dev(ANIMATE_PULSE_INLINE, scan_dirs),
            "console_residue":       dev(CONSOLE_PATTERN, scan_dirs),
            "inline_h1":             dev(H1_PATTERN, pages_dirs),
            "pages_missing_pageheader": _pages_missing_pageheader(pages_dirs, layout, root),
            "tables_no_pagination":     _tables_no_pagination(pages_dirs, layout, root),
        },
        "good_news": {
            "skeleton_importers":     len(grep_files(r"from\s+[\"']@/components/ui/skeleton[\"']", scan_dirs)),
            "tabular_nums_files":     len(grep_files(r"tabular-nums", scan_dirs)),
            "stale_while_revalidate": len(grep_files(r"loading && !data", pages_dirs)),
        },
    }

    if toolkit:
        primitives = toolkit_primitives(toolkit)
        state["primitive_adoption"] = primitive_adoption(primitives, scan_dirs, root)

    return state


def _list_pages(pages_dirs: list[Path], layout: str) -> list[Path]:
    """Mirror scan.sh's list_pages()."""
    out = []
    if not layout:
        return out
    if layout.startswith("vite"):
        for d in pages_dirs:
            if d.is_dir():
                out.extend(d.glob("*.tsx"))
    elif layout == "next.js app router":
        for d in pages_dirs:
            if d.is_dir():
                out.extend(d.rglob("page.tsx"))
                out.extend(d.rglob("*-content.tsx"))
    elif layout == "next.js pages router":
        for d in pages_dirs:
            if d.is_dir():
                out.extend(d.rglob("*.tsx"))
    # Dedupe + sort
    return sorted(set(out))


def _pages_missing_pageheader(pages_dirs: list[Path], layout: str, root: Path) -> dict:
    missing = []
    for f in _list_pages(pages_dirs, layout):
        try:
            if "<PageHeader" not in f.read_text():
                missing.append(str(f.relative_to(root)) if f.is_relative_to(root) else str(f))
        except Exception:
            pass
    return {"files": sorted(missing), "file_count": len(missing)}


def _tables_no_pagination(pages_dirs: list[Path], layout: str, root: Path) -> dict:
    offenders = []
    for f in _list_pages(pages_dirs, layout):
        try:
            text = f.read_text()
            if "<table" in text and "Pagination" not in text:
                offenders.append(str(f.relative_to(root)) if f.is_relative_to(root) else str(f))
        except Exception:
            pass
    return {"files": sorted(offenders), "file_count": len(offenders)}


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    root = Path(".").resolve()
    toolkit = None
    out_path = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--toolkit":
            toolkit = Path(args[i + 1]); i += 2
        elif a == "--out":
            out_path = Path(args[i + 1]); i += 2
        elif a.startswith("-"):
            print(f"Unknown flag: {a}", file=sys.stderr); sys.exit(2)
        else:
            root = Path(a).resolve(); i += 1

    state = collect(root, toolkit)
    payload = json.dumps(state, indent=2, sort_keys=False)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload)
        print(f"OK  {out_path}  ({len(payload)/1024:.1f} KB)", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()

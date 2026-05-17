#!/usr/bin/env python3
"""
toolkit_info.py — extract canonical info from a UI toolkit JSON spec.

Used by style-drift's scan.sh to derive the canonical primitive list, token
families, and component metadata from the toolkit JSON produced by
extract-toolkit. Splitting this out of scan.sh keeps the bash thin and the
JSON parsing in Python where it belongs.

Usage:
  toolkit_info.py <toolkit.json> summary       # human summary block
  toolkit_info.py <toolkit.json> primitives    # one primitive name per line
  toolkit_info.py <toolkit.json> components    # one component name per line
  toolkit_info.py <toolkit.json> tokens        # tab-separated  family<TAB>name
  toolkit_info.py <toolkit.json> field <key>   # print spec[key] verbatim
"""
import json
import re
import sys
from pathlib import Path


_PRIMITIVE_SECTION_HINTS = ("primitive", "primitives")


def _is_primitive_section(section: dict) -> bool:
    """A section qualifies as 'primitives' if its title contains the word.
    The extract-toolkit convention is sections like 'Form & action primitives',
    'Surface & layout primitives', 'Overlay primitives', 'Composite primitives'.
    """
    title = (section.get("title") or "").lower()
    return any(h in title for h in _PRIMITIVE_SECTION_HINTS)


def all_primitives(spec: dict) -> list[str]:
    out = []
    for section in spec.get("sections", []):
        if _is_primitive_section(section):
            out.extend(c.get("name", "") for c in section.get("components", []))
    return [n for n in out if n]


def all_components(spec: dict) -> list[str]:
    out = []
    for section in spec.get("sections", []):
        out.extend(c.get("name", "") for c in section.get("components", []))
    return [n for n in out if n]


def all_token_names(spec: dict) -> list[tuple[str, str]]:
    """Return flat list of (family, name) pairs across all token groups."""
    out = []
    for group_key, group in (spec.get("tokens") or {}).items():
        if isinstance(group, list):
            for entry in group:
                if isinstance(entry, list) and len(entry) >= 1:
                    out.append((group_key, entry[0]))
    return out


def print_summary(spec: dict) -> None:
    print(f"  Title:    {spec.get('title', '?')}")
    print(f"  Subtitle: {spec.get('subtitle', '?')}")
    print(f"  Version:  {spec.get('version', '?')}")
    if spec.get("stack"):
        print(f"  Stack:    {spec['stack']}")
    print()
    tokens = all_token_names(spec)
    print(f"  Tokens defined: {len(tokens)}")
    families = {}
    for fam, name in tokens:
        families.setdefault(fam, []).append(name)
    for fam in sorted(families.keys()):
        names = families[fam]
        # Wrap long lists for readability
        joined = ", ".join(names)
        if len(joined) > 80:
            joined = ", ".join(names[:6]) + f", … (+{len(names) - 6} more)"
        print(f"    {fam:14s} {joined}")
    print()
    primitives = all_primitives(spec)
    components = all_components(spec)
    print(f"  Components documented: {len(components)} ({len(primitives)} primitive)")
    if primitives:
        print(f"    Primitives: {', '.join(primitives)}")
    composite = [c for c in components if c not in primitives]
    if composite:
        print(f"    Composite + features: {', '.join(composite)}")


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    cmd  = sys.argv[2]
    if not path.exists():
        print(f"ERROR: toolkit JSON not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        spec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: not valid JSON: {path}: {e}", file=sys.stderr)
        sys.exit(2)

    if cmd == "summary":
        print_summary(spec)
    elif cmd == "primitives":
        for p in all_primitives(spec):
            print(p)
    elif cmd == "primitives-kebab":
        # Tab-separated: PascalName<TAB>kebab-name (for shadcn components/ui/ paths)
        for p in all_primitives(spec):
            kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", p).lower()
            print(f"{p}\t{kebab}")
    elif cmd == "components":
        for c in all_components(spec):
            print(c)
    elif cmd == "tokens":
        for fam, name in all_token_names(spec):
            print(f"{fam}\t{name}")
    elif cmd == "field":
        if len(sys.argv) < 4:
            print("Usage: toolkit_info.py <json> field <key>", file=sys.stderr)
            sys.exit(2)
        val = spec.get(sys.argv[3], "")
        print(val if not isinstance(val, (dict, list)) else json.dumps(val))
    else:
        print(f"Unknown cmd: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

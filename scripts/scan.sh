#!/usr/bin/env bash
# style-drift scan — sweep a React + Tailwind frontend for design-system drift.
#
# Usage:
#   scan.sh [frontend-root] [reference-path]
#
# If no frontend-root is given (or "."), the layout is auto-detected from the
# current working directory by probing in this order (matches extract-toolkit):
#   1. frontend/src/components       — Vite/CRA in a frontend/ subdir
#   2. src/components                — Vite/CRA at repo root
#   3. app/ + components/            — Next.js App Router
#   4. pages/ + components/          — Next.js Pages Router
#
# Prints a structured report grouped by deviation class. Each row is
#   file:line: <evidence>
# The caller (the model) is expected to read suspect files, rank severity,
# and produce the final report.
#
# Read-only: this script does not modify any file.

set -uo pipefail

ROOT="${1:-.}"
# REFERENCE can be:
#   - a path to a UI toolkit JSON (produced by extract-toolkit) → drives the
#     "Toolkit reference" header + primitive-adoption check
#   - any other path (markdown doc, Tailwind config) → informational only
#   - empty → uses bundled defaults only
REFERENCE="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TOOLKIT_JSON=""
if [[ -n "$REFERENCE" && "$REFERENCE" == *.json && -f "$REFERENCE" ]]; then
  TOOLKIT_JSON="$REFERENCE"
fi

if [ ! -d "$ROOT" ]; then
  echo "ERROR: frontend root not found: $ROOT" >&2
  exit 2
fi

# Detect layout (same probe order as extract-toolkit's "Inputs" section).
# SCAN_DIRS  = dirs walked for cross-cutting checks (color drift, anti-patterns, duplicates)
# PAGES_DIRS = dirs that hold "page-level" code (used by sections 3, 5, 11)
if   [ -d "$ROOT/frontend/src/components" ]; then
  LAYOUT="vite (frontend/src)"
  SCAN_DIRS=("$ROOT/frontend/src")
  PAGES_DIRS=("$ROOT/frontend/src/pages")
elif [ -d "$ROOT/src/components" ]; then
  LAYOUT="vite (src)"
  SCAN_DIRS=("$ROOT/src")
  PAGES_DIRS=("$ROOT/src/pages")
elif [ -d "$ROOT/app" ] && [ -d "$ROOT/components" ]; then
  LAYOUT="next.js app router"
  SCAN_DIRS=("$ROOT/app" "$ROOT/components")
  PAGES_DIRS=("$ROOT/app")
elif [ -d "$ROOT/pages" ] && [ -d "$ROOT/components" ]; then
  LAYOUT="next.js pages router"
  SCAN_DIRS=("$ROOT/pages" "$ROOT/components")
  PAGES_DIRS=("$ROOT/pages")
else
  echo "ERROR: $ROOT does not match a supported React frontend layout." >&2
  echo "Expected one of:" >&2
  echo "  frontend/src/components     (Vite/CRA in a frontend/ subdir)" >&2
  echo "  src/components              (Vite/CRA at repo root)" >&2
  echo "  app/ + components/          (Next.js App Router)" >&2
  echo "  pages/ + components/        (Next.js Pages Router)" >&2
  exit 2
fi

# ─── helpers ────────────────────────────────────────────────────────────────
header() {
  printf '\n\033[1;34m=== %s ===\033[0m\n' "$1"
}

# Strip ROOT/ prefix from a path for display.
relpath() {
  local p="$1"
  echo "${p#"$ROOT/"}"
}

count() {
  # Usage: count <label> <pattern> [scope-dir ...]
  # If no scope dirs are given, counts across all SCAN_DIRS.
  local label="$1"; shift
  local pattern="$1"; shift
  local dirs=()
  if [ "$#" -gt 0 ]; then
    dirs=("$@")
  else
    dirs=("${SCAN_DIRS[@]}")
  fi
  local n=0 c
  for d in "${dirs[@]}"; do
    if [ -d "$d" ]; then
      c=$(grep -rE --include="*.tsx" -l "$pattern" "$d" 2>/dev/null | wc -l | tr -d ' ')
      n=$((n + c))
    fi
  done
  printf '  %-46s %4s file(s)\n' "$label:" "$n"
}

show() {
  # Usage: show <label> <pattern> [limit]
  # Searches across all SCAN_DIRS.
  local label="$1"; shift
  local pattern="$1"; shift
  local limit="${1:-15}"
  printf '\n  \033[1m%s\033[0m\n' "$label"
  local hits
  hits=$(grep -rEn --include="*.tsx" "$pattern" "${SCAN_DIRS[@]}" 2>/dev/null | head -n "$limit")
  if [ -z "$hits" ]; then
    echo "    (clean)"
  else
    echo "$hits" | sed 's|^|    |'
  fi
}

# Enumerate "page-level" files for layout-specific iteration (section 5).
list_pages() {
  case "$LAYOUT" in
    "vite"*)
      for d in "${PAGES_DIRS[@]}"; do
        if [ -d "$d" ]; then
          for f in "$d"/*.tsx; do
            [ -f "$f" ] && echo "$f"
          done
        fi
      done
      ;;
    "next.js app router")
      for d in "${PAGES_DIRS[@]}"; do
        [ -d "$d" ] && find "$d" -type f \( -name "page.tsx" -o -name "*-content.tsx" \) 2>/dev/null
      done
      ;;
    "next.js pages router")
      for d in "${PAGES_DIRS[@]}"; do
        [ -d "$d" ] && find "$d" -type f -name "*.tsx" 2>/dev/null
      done
      ;;
  esac
}

# ─── overview ───────────────────────────────────────────────────────────────
header "Style Drift Scan"
echo "  Frontend root: $ROOT"
echo "  Layout:        $LAYOUT"
echo "  Scan dirs:     ${SCAN_DIRS[*]}"
echo "  Pages dirs:    ${PAGES_DIRS[*]}"
if [ -n "$TOOLKIT_JSON" ]; then
  echo "  Toolkit:       $TOOLKIT_JSON  (canonical reference)"
elif [ -n "$REFERENCE" ]; then
  echo "  Reference:     $REFERENCE  (informational; bundled patterns are used)"
fi

# ─── toolkit reference (only when a toolkit JSON is supplied) ───────────────
if [ -n "$TOOLKIT_JSON" ]; then
  header "0 · Toolkit reference (from $TOOLKIT_JSON)"
  python3 "$SCRIPT_DIR/toolkit_info.py" "$TOOLKIT_JSON" summary
fi

# ─── file-level overview ────────────────────────────────────────────────────
header "1 · File-level deviation summary"
count "gray-* (any kind)"             "(text|bg|border|divide|ring|hover:bg|hover:text|hover:border|focus:border|focus:ring)-gray-[0-9]"
count "zinc-* in pages (sidebar OK)"  "(text|bg|border)-zinc-" "${PAGES_DIRS[@]}"
count "animate-spin"                  "animate-spin"
count "animate-pulse"                 "animate-pulse"
count "console.log/warn"              "console\.(log|warn)"
count "raw fetch( in pages"           "fetch\(['\`]" "${PAGES_DIRS[@]}"

# ─── color family drift ─────────────────────────────────────────────────────
header "2 · Color family drift (gray vs slate)"
echo "  Toolkit-aligned codebases use slate-* for neutrals; gray-* is a Tailwind"
echo "  default that pre-dates most design-token migrations."
echo
echo "  Per-file gray-* counts:"
for d in "${SCAN_DIRS[@]}"; do
  grep -rE --include="*.tsx" -l "(text|bg|border|divide|ring|hover:bg|hover:text|hover:border|focus:border|focus:ring)-gray-[0-9]" "$d" 2>/dev/null
done | while read -r f; do
    n=$(grep -cE "(text|bg|border|divide|ring|hover:bg|hover:text|hover:border|focus:border|focus:ring)-gray-[0-9]" "$f")
    printf '    %4d  %s\n' "$n" "$(relpath "$f")"
  done | sort -rn
show "Sample evidence (first 12)" "(text|bg|border|divide|ring|hover:bg)-gray-[0-9]" 12

header "3 · Zinc creep (zinc-* outside the sidebar)"
echo "  Zinc is reserved for body bg + sidebar chrome. Appearance on a page surface"
echo "  signals drift."
have_pages=0
for d in "${PAGES_DIRS[@]}"; do
  [ -d "$d" ] && have_pages=1
done
if [ "$have_pages" -eq 1 ]; then
  printf '\n  \033[1m%s\033[0m\n' "Zinc usages in pages/"
  hits=$(grep -rEn --include="*.tsx" "(text|bg|border)-zinc-" "${PAGES_DIRS[@]}" 2>/dev/null | head -12)
  if [ -z "$hits" ]; then
    echo "    (clean — zinc only used in sidebar/layout, as intended)"
  else
    echo "$hits" | sed 's|^|    |'
  fi
else
  echo "    (no pages dir)"
fi

# ─── radii ──────────────────────────────────────────────────────────────────
header "4 · Card surface radii (should be rounded-xl)"
show "rounded-lg on bg-white surfaces" "bg-white[^\"]*rounded-(lg|md|sm)\\b" 15

# ─── missing primitives on pages ────────────────────────────────────────────
header "5 · Pages missing canonical primitives"
pages=$(list_pages)
if [ -n "$pages" ]; then
  echo "  Pages without <PageHeader (rolling their own h1 hero):"
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    if ! grep -q "<PageHeader" "$f"; then
      printf '    %s\n' "$(relpath "$f")"
    fi
  done <<< "$pages"

  echo
  echo "  Pages without useQueryFilters (rolling their own filter state):"
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    if ! grep -q "useQueryFilters" "$f"; then
      printf '    %s\n' "$(relpath "$f")"
    fi
  done <<< "$pages"

  echo
  echo "  Pages with <table but no <Pagination import:"
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    if grep -q "<table" "$f" && ! grep -q "Pagination" "$f"; then
      printf '    %s\n' "$(relpath "$f")"
    fi
  done <<< "$pages"

  echo
  echo "  Pages with <h1 (PageHeader is supposed to own h1):"
  grep -rEn --include="*.tsx" "<h1[^>]*>" "${PAGES_DIRS[@]}" 2>/dev/null | sed 's|^|    |' | head -10
else
  echo "    (no page-level files found under ${PAGES_DIRS[*]})"
fi

# ─── inline status chips that should use StatusBadge ────────────────────────
header "6 · Inline status chips bypassing <StatusBadge>"
show "Color-50 + color-700 chip pattern" "bg-(red|emerald|amber|blue|purple|green)-(50|100)[^\"]*text-(red|emerald|amber|blue|purple|green)-(600|700)" 10

# ─── anti-patterns ──────────────────────────────────────────────────────────
header "7 · Anti-patterns"
show "if (loading) return — no stale-while-revalidate guard" "if \\(loading\\) return" 8
show "animate-spin (toolkit prefers loading strips)" "animate-spin" 8
show "animate-pulse outside Skeleton.tsx" "animate-pulse" 12
show "key={state} on chart components"            "key=\\{[a-zA-Z_]+\\}" 6

# ─── duplicate inline components ────────────────────────────────────────────
header "8 · Duplicate inline component definitions"
echo "  Same component name defined inline in multiple files — promote to a shared primitive."
for name in Section PageHeader FilterBar KpiCard Subsection Card Panel; do
  files=$(grep -rEln "^function $name\\b" --include="*.tsx" "${SCAN_DIRS[@]}" 2>/dev/null)
  count=$(echo "$files" | grep -c . 2>/dev/null || true)
  if [ "${count:-0}" -ge 2 ]; then
    printf '    \033[1m%s\033[0m (%d copies):\n' "$name" "$count"
    echo "$files" | sed 's|^|      |'
  fi
done

# ─── eyebrow / label style variants ─────────────────────────────────────────
header "9 · Eyebrow label style variants"
echo "  Toolkit normally specifies one canonical class. If many variants appear,"
echo "  they probably need to be consolidated."
grep -rEh --include="*.tsx" "uppercase tracking-wid" "${SCAN_DIRS[@]}" 2>/dev/null \
  | sed -E 's/.*className="([^"]+)".*/\1/' \
  | tr -s ' ' \
  | sort -u \
  | head -20 | sed 's|^|    |'

# ─── console residue ────────────────────────────────────────────────────────
header "10 · console.log / console.warn residue"
show "Non-error console calls" "console\\.(log|warn)\\b" 12

# ─── good news ──────────────────────────────────────────────────────────────
header "11 · Patterns the codebase already gets right"
echo "  (these are the inverse signals — confirming what's working)"
swr=$(grep -rEln "loading && !data" --include="*.tsx" "${PAGES_DIRS[@]}" 2>/dev/null | wc -l | tr -d ' ')
phead=$(grep -rEln "<PageHeader" --include="*.tsx" "${PAGES_DIRS[@]}" 2>/dev/null | wc -l | tr -d ' ')
qfilt=$(grep -rEln "useQueryFilters" --include="*.tsx" "${PAGES_DIRS[@]}" 2>/dev/null | wc -l | tr -d ' ')
tabnums=$(grep -rEln "tabular-nums" --include="*.tsx" "${SCAN_DIRS[@]}" 2>/dev/null | wc -l | tr -d ' ')
printf '    %4d page(s) use stale-while-revalidate (loading && !data)\n' "$swr"
printf '    %4d page(s) use <PageHeader>\n' "$phead"
printf '    %4d page(s) use useQueryFilters\n' "$qfilt"
printf '    %4d file(s) use tabular-nums\n' "$tabnums"

# ─── primitive adoption (only when a toolkit JSON is supplied) ──────────────
if [ -n "$TOOLKIT_JSON" ]; then
  header "12 · Primitive adoption (from toolkit JSON)"
  echo "  For each canonical primitive in the toolkit, count files that import"
  echo "  it from components/ui/<kebab-name>. Low adoption suggests pages are"
  echo "  rolling their own. Imports from a sibling path don't count here."
  echo
  total=0
  unused=()
  while IFS=$'\t' read -r pascal kebab; do
    [ -z "$pascal" ] && continue
    total=$((total + 1))
    n=0
    for d in "${SCAN_DIRS[@]}"; do
      if [ -d "$d" ]; then
        c=$(grep -rEl --include="*.tsx" "from [\"']@/components/ui/${kebab}[\"']" "$d" 2>/dev/null | wc -l | tr -d ' ')
        n=$((n + c))
      fi
    done
    printf '    %-26s %3d file(s)\n' "$pascal" "$n"
    [ "$n" -eq 0 ] && unused+=("$pascal")
  done < <(python3 "$SCRIPT_DIR/toolkit_info.py" "$TOOLKIT_JSON" primitives-kebab)
  if [ "${#unused[@]}" -gt 0 ]; then
    echo
    echo "  ⚠ Zero-import primitives: ${unused[*]}"
    echo "    (either unused in code, exported under a different name,"
    echo "     or imported via a non-@/components/ui path)"
  fi
fi

# ─── summary line ───────────────────────────────────────────────────────────
header "Done"
total_gray=0
for d in "${SCAN_DIRS[@]}"; do
  if [ -d "$d" ]; then
    t=$(grep -rEc --include="*.tsx" "(text|bg|border|divide|ring|hover:bg|hover:text|hover:border|focus:border|focus:ring)-gray-[0-9]" "$d" 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
    total_gray=$((total_gray + t))
  fi
done
echo "  Total gray-* hits across all .tsx files: $total_gray"
echo "  Now read suspect files in context and rank severity."

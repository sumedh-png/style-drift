#!/usr/bin/env bash
# style-drift recon — detect the stack, styling system, token shape, component
# tree, and primitive library so the audit can pick the right recipes.
#
# Read-only. Emits a human-readable report to stdout AND writes a structured
# JSON snapshot to <root>/.style-drift/recon.json for downstream tools.
#
# Usage:
#   recon.sh [root]
#
# Exits 0 even when detection is incomplete — fields default to "unknown" /
# "none" / "" so the caller can ask the user to fill gaps.

set -uo pipefail

ROOT="${1:-.}"
OUT_DIR="$ROOT/.style-drift"
OUT_JSON="$OUT_DIR/recon.json"

if [ ! -d "$ROOT" ]; then
  echo "ERROR: root not found: $ROOT" >&2
  exit 2
fi

STACK="unknown"        # web | mobile | desktop | mobile-or-jvm | unknown
FRAMEWORK="none"       # react | next.js | vue | svelte | angular | solid | react-native | flutter | swift-ios | android | js-unknown | none
FILE_EXT=""            # .tsx | .jsx | .vue | .svelte | .dart | .swift | .kt | ""
declare -a SOURCE_ROOTS=()
STYLING="unknown"      # tailwind | css-modules | styled-components | emotion | inline-style | sfc-scoped-css | rn-stylesheet | flutter-themedata | vanilla-css | unknown (may be combined with +)
TOKENS="none"          # tailwind-config | css-vars | theme-object | design-tokens-json | none (may be combined with +)
TREE="unknown"         # standard-tree | single-file-monolith | few-large-files | unknown
PRIMITIVES="none"      # shadcn | radix | mui | chakra | mantine | rn-paper | custom-ui-dir | in-file | none (may be combined with +)
LARGEST_FILE=""
LARGEST_LINES=0
TOTAL_SRC=0

# ─── 1. Framework / language ────────────────────────────────────────────────
# Probe package.json at root AND at common subdirs (monorepos, frontend/ split).
PKG=""
for cand in "$ROOT" "$ROOT/frontend" "$ROOT/client" "$ROOT/web" "$ROOT/app"; do
  if [ -f "$cand/package.json" ]; then PKG="$cand/package.json"; break; fi
done

if [ -f "$ROOT/pubspec.yaml" ] && grep -q "flutter:" "$ROOT/pubspec.yaml" 2>/dev/null; then
  STACK="mobile"; FRAMEWORK="flutter"; FILE_EXT=".dart"
  [ -d "$ROOT/lib" ] && SOURCE_ROOTS+=("$ROOT/lib")
elif ls "$ROOT"/*.xcodeproj >/dev/null 2>&1 || ls "$ROOT"/*.xcworkspace >/dev/null 2>&1; then
  STACK="mobile"; FRAMEWORK="swift-ios"; FILE_EXT=".swift"
elif [ -f "$ROOT/build.gradle.kts" ] || [ -f "$ROOT/build.gradle" ]; then
  STACK="mobile-or-jvm"; FRAMEWORK="android"; FILE_EXT=".kt"
elif [ -n "$PKG" ]; then
  if   grep -q '"react-native"' "$PKG" 2>/dev/null; then STACK="mobile"; FRAMEWORK="react-native"
  elif grep -q '"next"'         "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="next.js"
  elif grep -q '"nuxt"'         "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="nuxt"
  elif grep -q '"vue"'          "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="vue"
  elif grep -q '"svelte"'       "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="svelte"
  elif grep -q '"@angular/core"' "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="angular"
  elif grep -q '"solid-js"'     "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="solid"
  elif grep -q '"react"'        "$PKG" 2>/dev/null; then STACK="web"; FRAMEWORK="react"
  else STACK="web"; FRAMEWORK="js-unknown"
  fi
  pkgdir="$(dirname "$PKG")"
  if   [ -f "$pkgdir/tsconfig.json" ]; then FILE_EXT=".tsx"
  else FILE_EXT=".jsx"
  fi
fi

# ─── 2. Source root probing ─────────────────────────────────────────────────
if [ ${#SOURCE_ROOTS[@]} -eq 0 ]; then
  for cand in frontend/src src app pages components lib; do
    [ -d "$ROOT/$cand" ] && SOURCE_ROOTS+=("$ROOT/$cand")
  done
fi
# Deduplicate while preserving order (portable — mapfile is bash 4+)
if [ ${#SOURCE_ROOTS[@]} -gt 0 ]; then
  _seen=""
  _dedup=()
  for d in "${SOURCE_ROOTS[@]}"; do
    case ":$_seen:" in *":$d:"*) ;; *) _dedup+=("$d"); _seen="$_seen:$d" ;; esac
  done
  SOURCE_ROOTS=("${_dedup[@]}")
fi
# Fall back to ROOT if nothing matched (avoids empty-array failures below)
[ ${#SOURCE_ROOTS[@]} -eq 0 ] && SOURCE_ROOTS=("$ROOT")

# ─── 3. Source extension list (driven by framework) ─────────────────────────
case "$FRAMEWORK" in
  flutter)             EXTS=("*.dart") ;;
  swift-ios)           EXTS=("*.swift") ;;
  android)             EXTS=("*.kt" "*.java" "*.xml") ;;
  vue|nuxt)            EXTS=("*.vue" "*.ts" "*.js") ;;
  svelte)              EXTS=("*.svelte" "*.ts" "*.js") ;;
  angular)             EXTS=("*.ts" "*.html" "*.scss" "*.css") ;;
  *)                   EXTS=("*.tsx" "*.jsx" "*.ts" "*.js") ;;
esac

# Build a `find` predicate
find_args=()
for e in "${EXTS[@]}"; do
  if [ ${#find_args[@]} -gt 0 ]; then find_args+=("-o"); fi
  find_args+=("-name" "$e")
done

# ─── 4. Largest source file + total file count ──────────────────────────────
for d in "${SOURCE_ROOTS[@]}"; do
  [ -d "$d" ] || continue
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    n=$(wc -l < "$f" 2>/dev/null | tr -d ' ')
    [ -z "$n" ] && continue
    if [ "$n" -gt "$LARGEST_LINES" ]; then LARGEST_LINES=$n; LARGEST_FILE="$f"; fi
    TOTAL_SRC=$((TOTAL_SRC + 1))
  done < <(find "$d" -type f \( "${find_args[@]}" \) 2>/dev/null)
done

# ─── 5. Tree-shape heuristic ────────────────────────────────────────────────
if   [ "$TOTAL_SRC" -le 6 ]  && [ "$LARGEST_LINES" -gt 5000 ]; then TREE="single-file-monolith"
elif [ "$TOTAL_SRC" -le 20 ] && [ "$LARGEST_LINES" -gt 2000 ]; then TREE="few-large-files"
elif [ "$TOTAL_SRC" -gt 20 ]; then TREE="standard-tree"
fi

# ─── 6. Styling system ──────────────────────────────────────────────────────
add_styling() {
  local v="$1"
  if [ "$STYLING" = "unknown" ]; then STYLING="$v"
  elif [[ "$STYLING" != *"$v"* ]]; then STYLING="$STYLING+$v"
  fi
}

# Tailwind
if [ -f "$ROOT/tailwind.config.js" ] || [ -f "$ROOT/tailwind.config.ts" ] || [ -f "$ROOT/tailwind.config.cjs" ] || [ -f "$ROOT/tailwind.config.mjs" ]; then
  add_styling "tailwind"
fi
# Stack-implied styling
case "$FRAMEWORK" in
  vue|nuxt)     add_styling "sfc-scoped-css" ;;
  svelte)       add_styling "sfc-scoped-css" ;;
  flutter)      add_styling "flutter-themedata" ;;
  react-native) add_styling "rn-stylesheet" ;;
  swift-ios)    add_styling "swiftui" ;;
  android)      add_styling "android-xml-or-compose" ;;
esac
# CSS Modules
for d in "${SOURCE_ROOTS[@]}"; do
  [ -d "$d" ] || continue
  if find "$d" -maxdepth 8 -name "*.module.css" 2>/dev/null | head -1 | grep -q .; then
    add_styling "css-modules"; break
  fi
done
# styled-components / emotion
if [ -f "$ROOT/package.json" ]; then
  grep -q '"styled-components"' "$ROOT/package.json" 2>/dev/null && add_styling "styled-components"
  grep -q '"@emotion' "$ROOT/package.json"           2>/dev/null && add_styling "emotion"
  grep -q '"@stitches/react"' "$ROOT/package.json"   2>/dev/null && add_styling "stitches"
  grep -q '"@stylex/' "$ROOT/package.json"           2>/dev/null && add_styling "stylex"
  grep -q '"unocss"' "$ROOT/package.json"            2>/dev/null && add_styling "unocss"
fi
# Inline-style density — runs on any JS/TS-flavoured stack since framework
# detection can fail when the JSX file has no react import or when the project
# imports React indirectly. `style={{ ... }}` is JSX-only syntax.
inline_count=0
for d in "${SOURCE_ROOTS[@]}"; do
  [ -d "$d" ] || continue
  n=$(find "$d" -type f \( -name "*.tsx" -o -name "*.jsx" -o -name "*.ts" -o -name "*.js" \) -exec grep -hoE 'style=\{\{' {} + 2>/dev/null | wc -l | tr -d ' ')
  inline_count=$((inline_count + n))
done
if [ "$inline_count" -gt 500 ]; then
  add_styling "inline-style"
  # If framework detection said "unknown" but we see heavy JSX inline styles,
  # promote to react (the file extension supports it).
  if [ "$FRAMEWORK" = "none" ] || [ "$FRAMEWORK" = "unknown" ]; then
    STACK="web"; FRAMEWORK="react"
    [ -z "$FILE_EXT" ] && FILE_EXT=".jsx"
  fi
fi
# Vanilla CSS fallback
if [ "$STYLING" = "unknown" ]; then
  for d in "${SOURCE_ROOTS[@]}" "$ROOT"; do
    [ -d "$d" ] || continue
    if find "$d" -maxdepth 6 -name "*.css" -not -name "*.module.css" 2>/dev/null | head -1 | grep -q .; then
      add_styling "vanilla-css"; break
    fi
  done
fi

# ─── 7. Token shape ─────────────────────────────────────────────────────────
add_tokens() {
  local v="$1"
  if [ "$TOKENS" = "none" ]; then TOKENS="$v"
  elif [[ "$TOKENS" != *"$v"* ]]; then TOKENS="$TOKENS+$v"
  fi
}

[[ "$STYLING" == *tailwind* ]] && add_tokens "tailwind-config"

# CSS variables in :root
for d in "${SOURCE_ROOTS[@]}" "$ROOT"; do
  [ -d "$d" ] || continue
  if grep -rEl --include="*.css" --include="*.scss" ":root[[:space:]]*\{[^}]*--" "$d" 2>/dev/null | head -1 | grep -q .; then
    add_tokens "css-vars"; break
  fi
done

# JS theme object (heuristic: a const named THEMES/themes/theme = { with bg/color keys)
for d in "${SOURCE_ROOTS[@]}"; do
  [ -d "$d" ] || continue
  if grep -rElE --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" '(const|export const)[[:space:]]+(THEMES|themes|theme|tokens|palette)[[:space:]]*=' "$d" 2>/dev/null | head -1 | grep -q .; then
    add_tokens "theme-object"; break
  fi
done

# Design-tokens JSON
if find "$ROOT/docs" "$ROOT/tokens" "$ROOT/design" -maxdepth 3 -type f -name "*token*.json" 2>/dev/null | head -1 | grep -q . ; then
  add_tokens "design-tokens-json"
fi

# ─── 8. Primitive library ───────────────────────────────────────────────────
add_primitives() {
  local v="$1"
  if [ "$PRIMITIVES" = "none" ]; then PRIMITIVES="$v"
  elif [[ "$PRIMITIVES" != *"$v"* ]]; then PRIMITIVES="$PRIMITIVES+$v"
  fi
}

[ -f "$ROOT/components.json" ] && add_primitives "shadcn"
if [ -f "$ROOT/package.json" ]; then
  grep -q '"@radix-ui/'         "$ROOT/package.json" 2>/dev/null && add_primitives "radix"
  grep -q '"@mui/'              "$ROOT/package.json" 2>/dev/null && add_primitives "mui"
  grep -q '"@chakra-ui/'        "$ROOT/package.json" 2>/dev/null && add_primitives "chakra"
  grep -q '"@mantine/'          "$ROOT/package.json" 2>/dev/null && add_primitives "mantine"
  grep -q '"@ariakit/'          "$ROOT/package.json" 2>/dev/null && add_primitives "ariakit"
  grep -q '"react-native-paper"' "$ROOT/package.json" 2>/dev/null && add_primitives "rn-paper"
  grep -q '"@gluestack-ui/'     "$ROOT/package.json" 2>/dev/null && add_primitives "gluestack"
  grep -q '"@tamagui/'          "$ROOT/package.json" 2>/dev/null && add_primitives "tamagui"
  grep -q '"flutter_material"'  "$ROOT/pubspec.yaml" 2>/dev/null && add_primitives "flutter-material"
fi
# Custom components/ui dir
for d in "${SOURCE_ROOTS[@]}"; do
  if [ -d "$d/components/ui" ] || [ -d "$d/ui" ] || [ -d "$d/Components/UI" ]; then
    add_primitives "custom-ui-dir"; break
  fi
done
# In-file primitives — only meaningful when tree is monolithic
if [ "$TREE" = "single-file-monolith" ] && [ -n "$LARGEST_FILE" ]; then
  if grep -qE '^(const|function)[[:space:]]+(Btn|Badge|Card|Button|Chip|Tag|Pill)\b' "$LARGEST_FILE" 2>/dev/null; then
    add_primitives "in-file"
  fi
fi

# ─── 9. Render report ───────────────────────────────────────────────────────
echo
echo "── Style Drift · Reconnaissance ──"
echo "  root:          $ROOT"
echo "  stack:         $STACK"
echo "  framework:     $FRAMEWORK"
echo "  file ext:      $FILE_EXT"
echo "  source roots:  ${SOURCE_ROOTS[*]}"
echo "  styling:       $STYLING"
echo "  tokens:        $TOKENS"
echo "  primitives:    $PRIMITIVES"
echo "  tree shape:    $TREE"
echo "  source files:  $TOTAL_SRC"
if [ -n "$LARGEST_FILE" ]; then
  echo "  largest file:  $LARGEST_FILE  ($LARGEST_LINES lines)"
fi
echo

# ─── 10. Recipe routing hint ────────────────────────────────────────────────
echo "── Recipe routing ──"
case "$STYLING" in
  *tailwind*)              echo "  primary recipes:  Tailwind (run scan.sh + tailwind recipes in SKILL.md)" ;;
  *inline-style*)          echo "  primary recipes:  inline-style + theme-object" ;;
  *rn-stylesheet*)         echo "  primary recipes:  React Native StyleSheet" ;;
  *flutter-themedata*)     echo "  primary recipes:  Flutter ThemeData" ;;
  *sfc-scoped-css*)        echo "  primary recipes:  Vue/Svelte SFC scoped CSS" ;;
  *css-modules*)           echo "  primary recipes:  CSS Modules + token files" ;;
  *styled-components*|*emotion*) echo "  primary recipes:  CSS-in-JS tagged templates" ;;
  vanilla-css)             echo "  primary recipes:  vanilla CSS (token-by-naming-convention)" ;;
  *)                       echo "  primary recipes:  unknown — ask user which conventions apply" ;;
esac
if [ "$TREE" = "single-file-monolith" ]; then
  echo "  tree note:        monolith → A03 (Application convention) is automatically Major;"
  echo "                    every other axis recipe greps the single file rather than walking a tree"
fi
echo

# ─── 11. JSON snapshot ──────────────────────────────────────────────────────
mkdir -p "$OUT_DIR" 2>/dev/null || true
{
  printf '{\n'
  printf '  "root": "%s",\n' "$ROOT"
  printf '  "stack": "%s",\n' "$STACK"
  printf '  "framework": "%s",\n' "$FRAMEWORK"
  printf '  "file_ext": "%s",\n' "$FILE_EXT"
  printf '  "source_roots": ['
  first=1
  for d in "${SOURCE_ROOTS[@]}"; do
    [ $first -eq 1 ] || printf ', '
    printf '"%s"' "$d"; first=0
  done
  printf '],\n'
  printf '  "styling": "%s",\n' "$STYLING"
  printf '  "tokens": "%s",\n' "$TOKENS"
  printf '  "primitives": "%s",\n' "$PRIMITIVES"
  printf '  "tree": "%s",\n' "$TREE"
  printf '  "total_source_files": %d,\n' "$TOTAL_SRC"
  printf '  "largest_file": "%s",\n' "$LARGEST_FILE"
  printf '  "largest_lines": %d\n' "$LARGEST_LINES"
  printf '}\n'
} > "$OUT_JSON" 2>/dev/null || true

echo "  recon JSON: $OUT_JSON"

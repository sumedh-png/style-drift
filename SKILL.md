---
name: style-drift
description: Audit any frontend codebase — React/Vue/Svelte/Angular/Solid/React Native/Flutter/SwiftUI/Compose, with Tailwind, CSS Modules, styled-components/emotion, inline styles, vanilla CSS, or any combination — for design-system drift across 14 UX axes (primitives, library convention, application convention, color tokens, typography, radii, responsiveness/grids, accessibility, motion, forms, data display, dark/theme mode, hygiene, responsiveness/tables). A reconnaissance step detects stack, styling system, token shape, primitive library, and tree shape, then the audit picks recipes that match — so the same skill works on a Tailwind+shadcn app, a Vue SFC project, a React Native screen, or a single 30K-line inline-style React monolith. Use whenever the user asks to "find style deviations / audit the UI / scan for design drift / token drift / style inconsistencies / check UI consistency against the design system or toolkit", or wants a list of files that don't match a documented design reference. Especially useful right after a design-system or toolkit doc is created or updated, to catalog what still needs to be brought into line. Returns an axis catalog (Major / Significant / Minor / OK) plus a self-contained visual-preview HTML showing per-axis BEFORE/AFTER comparisons and a full-page BEFORE/AFTER mockup of the worst-offending page — the user reviews the preview and confirms before any edits are applied. NOT for runtime visual-regression testing (use Chromatic/Percy for that) and NOT for ESLint-style formatting issues.
---

# Style Drift — frontend design-system audit (stack-agnostic)

A repeatable way to scan **any** frontend for drift across 14 UX axes. Adapts to the project's stack via a reconnaissance step, then picks recipes that match the detected styling system. Produces an axis-organised report you can act on or hand to a follow-up coding task.

## When to fire

- "Find style/UI deviations" / "scan for design drift" / "audit the UI"
- "Check (frontend|src) for inconsistencies with (toolkit|design system|tokens)"
- "Where are we still using gray vs slate?" — or any specific token-drift question
- Right after a design-system doc (e.g. `docs/ui-toolkit.pdf`, `docs/design-tokens.md`) is created or updated, to inventory what needs migrating
- "Cover responsiveness / accessibility / dark mode / forms" — any specific axis

## When NOT to fire

- One-off "what does this component look like?" — that's a Read, not an audit
- ESLint/Prettier issues — different toolchain
- Visual regression — use Chromatic, Percy, or screenshot-diffing tools
- Cross-page user-flow issues — that's QA, not styling drift

## Stack-agnostic by design

The same 14 axes apply to every frontend stack — what changes is the *recipe* used to gather evidence. The skill handles this in two passes:

1. **Recon** (`scripts/recon.sh`) detects the stack, styling system, token shape, tree shape, and primitive library, then writes a structured snapshot to `<root>/.style-drift/recon.json`.
2. **Audit** runs the recipes that match what recon found. Recipe families included in this doc:

| Recon `styling` value | Primary recipe family |
|---|---|
| `tailwind` | Tailwind utility-class greps (also run `scripts/scan.sh`) |
| `css-modules` | `*.module.css` + token-file greps |
| `styled-components` / `emotion` / `stitches` | tagged-template greps |
| `inline-style` | `style={{ ... }}` literal greps + token-object adoption |
| `sfc-scoped-css` (Vue / Svelte) | `<style scoped>` block greps |
| `rn-stylesheet` (React Native) | `StyleSheet.create({})` literal greps + `Dimensions` / `useWindowDimensions` checks |
| `flutter-themedata` (Flutter) | `ThemeData` + `TextStyle` greps + `MediaQuery` checks |
| `vanilla-css` / `scss` | per-file class definitions + `:root --var` greps |
| `swiftui` / `android-xml-or-compose` | platform-specific greps (sketched; ask user to refine) |

If recon returns combinations (e.g. `tailwind+css-modules`), run **both** recipe families and de-duplicate findings.

## Inputs

- **Root** (required): the project root or a subdir to audit. The bundled `scripts/recon.sh` probes from this path automatically. If `recon.sh` returns `framework: js-unknown` or `styling: unknown`, ask the user to confirm before continuing.
- **Canonical reference** (strongly recommended): a path to the design-system spec. Accepted forms:
  - **A UI toolkit JSON file** (`docs/ui-toolkit.json`, produced by `extract-toolkit`) — the preferred grounding source.
  - A markdown doc (`docs/ui-toolkit.md`, `CLAUDE.md`) — informational only.
  - A Tailwind config (`tailwind.config.*`) — informational only.
  - A design-tokens JSON (Style Dictionary format, etc.) — informational.
  - No reference — recon's detected token shape becomes the de-facto canonical.
- **Scope filter** (optional): a single axis (`A01`, `A07`, etc.) or a glob. Default: full 14-axis audit.

## The 14 axes (intent-stated, stack-agnostic)

Every audit produces an **axis catalog** with one row per axis. Status:

- 🔴 **Major** — whole-app primitive missing; a11y/structural violation; semantic break visible to screen readers / mobile users
- 🟠 **Significant** — design-token gap that forces workarounds across many files; primitive exists but ~30%+ of call sites bypass it
- 🟡 **Minor** — cosmetic; isolated; fixable in a single sweep
- 🟢 **OK** — confirmed working; surfaces this so the report doesn't read as just complaints

| # | Axis | Intent (stack-agnostic) |
|---|---|---|
| **A01** | **Primitives** | Adoption rate of the project's UI primitives vs raw platform elements. *Primitive set* depends on recon: `shadcn` / `radix` / `mui` / `chakra` / `mantine` / `rn-paper` / custom `components/ui/` / `in-file` Btn-Badge-Card / `flutter-material` / `swiftui`. *Raw element* depends on framework: `<button>`/`<input>` for web, `<Pressable>`/`<TextInput>` for RN, `ElevatedButton`/`TextField` for Flutter, `Button { }` for SwiftUI, `<Button>` for Compose. |
| **A02** | **Library convention** | When the primitive library has a variant/tone enum (shadcn, MUI, Mantine, RN-Paper), measure how often call sites use `className`/`style` overrides to fight the enum. N/A for stacks with no formal variant system (raw inline styles, inline primitives). |
| **A03** | **Application convention** | Project-level page chrome — header, breadcrumb, pagination, filter-state hook, error/empty/loading slots. Tree-shape matters: `single-file-monolith` is automatically Major because there *can't be* a shared chrome primitive when everything is inline. |
| **A04** | **Color tokens** | Raw color literals (`#hex`, `rgb()`, `hsl()`, named colors) that bypass the project's token system. Token system from recon: `tailwind-config` / `css-vars` / `theme-object` / `design-tokens-json` / `none`. |
| **A05** | **Typography** | Semantic heading order (h1 → h2 → h3) on web, equivalent on mobile (RN `accessibilityRole="header"`, Flutter `Semantics(header: true)`). Heading-style variance across files. fontSize-ladder spread. |
| **A06** | **Radii** | Distribution of corner-radius values against an intended scale. Bare/default values that resolve to a fallback. |
| **A07** | **Responsiveness · grids** | Web: mobile-first column counts, breakpoint coverage. RN/Flutter: `useWindowDimensions`/`MediaQuery` adaptive layouts. Native: size-class branching. A 0-breakpoint web app is desktop-only and counts as Major. |
| **A08** | **Accessibility** | aria-*, role, sr-only, alt= on web. `accessibilityLabel`/`accessibilityRole` on RN. `Semantics()` on Flutter. `.accessibilityLabel()` on SwiftUI. `contentDescription` on Compose. Plus semantic heading order and reduced-motion gate. |
| **A09** | **Motion** | Transition/animation usage + the reduced-motion gate (`prefers-reduced-motion` on web; `AccessibilityInfo.isReduceMotionEnabled` on RN; `MediaQuery.disableAnimations` on Flutter). |
| **A10** | **Forms** | Adoption of Input/Select/Switch/Label primitives vs raw text-entry elements. Label-association correctness (`htmlFor`/`id` on web; `accessibilityLabel` on RN; etc). |
| **A11** | **Data display** | Numeric-column alignment (web `tabular-nums`, RN `fontVariant`, Flutter `FontFeature.tabularFigures`). Shared formatter modules vs per-file fmt helpers. Chart palette consistency. |
| **A12** | **Dark/theme mode** | Coverage of theme variants. Web: `dark:` Tailwind pairs OR CSS-var palettes that flip on `[data-theme=dark]` OR token-object branching. RN: `useColorScheme`. Flutter: `ThemeMode`. |
| **A13** | **Hygiene** | console residue (web), `print()`/`debugPrint()` (Flutter), `Log.d` (Android), `print()` (Swift). TODO/FIXME age. `as any` / `!.` force-unwraps / `_ in` ignored params. |
| **A14** | **Responsiveness · tables** (or lists) | Web: tables overflow, sticky headers, column-hiding strategy. RN/Flutter: `FlatList`/`ListView` adaptive item layouts, no horizontal overflow. |

## Workflow

### Step 0 · Reconnaissance (mandatory)

```bash
~/.claude/skills/style-drift/scripts/recon.sh <root>
```

Prints a recon report and writes `<root>/.style-drift/recon.json`. Read both. The `styling`, `tokens`, `tree`, and `primitives` fields tell you which recipes to run in Step 2.

**Cold-stack handling.** If recon prints `unknown` for `styling` or `framework`:
- Look at `largest_file` for clues (file extension, imports, top-level patterns).
- Ask the user one focused question: *"Recon couldn't determine the styling system — is this Tailwind / CSS modules / styled-components / inline styles / something else?"*
- Don't guess silently. Wrong recipe = wrong audit.

**Recon-driven status adjustments.** Apply these *before* gathering evidence:
- `tree: single-file-monolith` → **A03 is automatically Major.** Skip the "find pages without breadcrumb" recipe (no pages exist); explain in evidence that the monolith itself is the structural problem.
- `tree: few-large-files` → A03 starts at Significant. Most page-chrome recipes still apply per file.
- `primitives: none` AND `styling: inline-style` → **A01 is automatically Major.** No primitive layer exists to adopt.
- `tokens: none` → **A04 is automatically Major.** No token system to bypass; every color literal is technically "raw".
- `framework: flutter` / `swift-ios` / `android` → A07 (grids) and A14 (tables) become "adaptive layouts" — different recipes apply.

### Step 1 · Stack-specific accelerator (optional)

Only useful when recon says `styling: tailwind` and `framework` is React/Next.js. `scan.sh` covers ~7 of the 14 axes mechanically for that exact combo:

```bash
~/.claude/skills/style-drift/scripts/scan.sh <root> docs/ui-toolkit.json  # preferred
~/.claude/skills/style-drift/scripts/scan.sh <root>                       # no toolkit
```

For any other stack, skip Step 1 and go straight to Step 2.

### Step 2 · Run axis recipes (selected by recon)

For each of the 14 axes, run **the recipe block whose stack matches recon**. These are read-only greps — no side effects. Parallelise: run all recipes in a single message with multiple Bash tool calls.

**Greps surface volume. They do not produce an audit.** Treat the grep output as a list of *suspects to investigate*, not as the finding itself. Step 2b (mandatory) converts grep counts into named-component diagnoses.

Each axis block below has:
- **Intent** — what the axis measures (stack-agnostic)
- **Recipes** — concrete greps grouped by stack family (run the rows that match recon)

---

#### A01 · Primitives

**Intent**: How often call sites use the project's primitive layer vs raw platform elements.

```bash
# Tailwind + React (custom-ui-dir):
for f in components/ui/*.tsx; do n=$(basename "$f" .tsx); \
  cnt=$(grep -rln "from \"@/components/ui/$n\"" --include="*.tsx" app/ components/ 2>/dev/null | wc -l | tr -d ' '); \
  echo "  $n  →  $cnt files"; done
grep -roE '<button\b' --include="*.tsx" app/ components/ | wc -l
grep -rln '<input type=' --include="*.tsx" app/ components/ | wc -l

# Inline-style + React (in-file primitives, monolith):
# Count uses of each primitive declared in the file vs the raw HTML tag.
grep -cE '<Btn\b'    "$LARGEST"     # primitive usages
grep -cE '<button\b' "$LARGEST"     # raw bypass
grep -cE '<Badge\b'  "$LARGEST"
grep -cE '<Card\b'   "$LARGEST"

# Vue / Svelte SFC:
grep -rln "from ['\"].*ui/Button" --include="*.vue" src/ | wc -l
grep -rcE '<button\b'  --include="*.vue" src/

# React Native:
grep -rln "from ['\"]react-native-paper" --include="*.tsx" src/ | wc -l
grep -rcE '<Pressable\b|<TouchableOpacity\b|<TouchableHighlight\b' --include="*.tsx" src/

# Flutter:
grep -rcE '\bElevatedButton\(|\bFilledButton\(|\bTextButton\(|\bOutlinedButton\(' --include="*.dart" lib/
grep -rcE '\bGestureDetector\(|\bInkWell\(' --include="*.dart" lib/  # bypass signals
```

---

#### A02 · Library convention

**Intent**: For stacks with a formal variant/tone API, count overrides that fight it.

```bash
# shadcn / Radix (className override on top of variant=):
grep -rnE '<(Badge|Button)[^>]*(variant|tone)="[^"]*"[^>]*className=' --include="*.tsx" app/ components/

# MUI (sx prop override on top of variant=):
grep -rnE '<(Button|Chip)[^>]*variant=[^>]*sx=' --include="*.tsx" src/

# Mantine (similar):
grep -rnE '<(Button|Badge)[^>]*variant=[^>]*style=' --include="*.tsx" src/

# Inline-style + in-file primitives: N/A — no enum to fight. Report as OK · N/A.
```

---

#### A03 · Application convention

**Intent**: Project-level page chrome. Heavily dependent on tree shape.

```bash
# Standard tree — pages without canonical chrome:
grep -rln "<PageHeader\|<Breadcrumb\|<Pagination" --include="*.tsx" app/ | wc -l
# vs total pages:
find app -name "page.tsx" -o -name "*-content.tsx" | wc -l

# Monolith — A03 is automatically Major. Report:
wc -l "$LARGEST"
grep -cE '^(const|function)\s+[A-Z][A-Za-z0-9]+' "$LARGEST"   # component count

# Vue SFC — pages without <PageHeader> import:
grep -rlE "import\s+PageHeader\s+from" --include="*.vue" src/pages/
```

---

#### A04 · Color tokens

**Intent**: Raw color literals that bypass the project's token system.

```bash
# Tailwind — gray vs slate, named color creep:
grep -roE '(text|bg|border|divide|ring)-(gray|zinc|neutral|stone)-[0-9]+' --include="*.tsx" app/ components/ | sort | uniq -c

# Inline-style — hex/rgb literals vs token references:
grep -oE '#[0-9a-fA-F]{6}\b' "$LARGEST" | sort | uniq -c | sort -rn | head -20
grep -oE 'T\.[a-zA-Z][a-zA-Z0-9.]*' "$LARGEST" | wc -l   # or theme.* / palette.* / tokens.* — substitute the project's accessor; allow dotted paths

# Case-mixed duplicates (smoking gun for "format jitter, not intent"):
#   Same color appearing in upper- and lower-case form (#F59E0B and #f59e0b) means
#   contributors typed hex by hand. Lowercase the output and re-uniq — the count
#   drop is the duplication signal.
grep -oE '#[0-9a-fA-F]{6}\b' "$LARGEST" | tr 'A-F' 'a-f' | sort -u | wc -l   # distinct colors when normalised
grep -oE '#[0-9a-fA-F]{6}\b' "$LARGEST" | sort -u | wc -l                    # distinct as-typed

# CSS Modules — hex in module files (excluding token files):
grep -rnE '#[0-9a-fA-F]{6}' --include="*.module.css" src/ | grep -v 'tokens\|theme\|variables'

# styled-components / emotion — hex in tagged templates:
grep -rnE '`[^`]*#[0-9a-fA-F]{6}' --include="*.tsx" --include="*.ts" src/

# RN StyleSheet — color literals in create blocks:
grep -rnE 'color:\s*[\x27"]#[0-9a-fA-F]+' --include="*.tsx" src/

# Flutter — Color(0xFF...) bypassing Theme.of(context).colorScheme:
grep -rnE 'Color\(0x[0-9A-Fa-f]+\)|Colors\.[a-z]+' --include="*.dart" lib/

# Vanilla CSS — hex outside :root token block:
grep -rnE '#[0-9a-fA-F]{6}' --include="*.css" src/ | grep -v ':root\|--'
```

---

#### A05 · Typography

**Intent**: Semantic heading order + heading-style variance + fontSize scale spread.

```bash
# Web (Tailwind or any web stack) — h1 class variance, multi-h1 pages:
grep -rEn '<h1\s' --include="*.tsx" --include="*.vue" --include="*.svelte" app/ src/
for f in $(find app -name "page.tsx"); do c=$(grep -c "<h1" "$f"); [ "$c" -gt 1 ] && echo "$c h1s · $f"; done
grep -rEh 'uppercase tracking-wid' --include="*.tsx" app/ | sed -E 's/.*className="([^"]+)".*/\1/' | sort -u

# Inline-style + monolith — fontSize ladder spread (catches decimals like 10.5):
grep -oE 'fontSize:\s*[0-9.]+' "$LARGEST" | sort | uniq -c | sort -rn | head -25
grep -cE '<h[1-6]\b' "$LARGEST"   # 0 = no semantic headings = Major

# letterSpacing format jitter — same intent, different syntax:
grep -oE 'letterSpacing:\s*"\.?0?\.0[0-9]em"' "$LARGEST" | sort | uniq -c | sort -rn

# RN — heading semantics:
grep -rnE 'accessibilityRole="header"' --include="*.tsx" src/ | wc -l

# Flutter:
grep -rnE 'Semantics\([^)]*header:\s*true' --include="*.dart" lib/ | wc -l
```

---

#### A06 · Radii

**Intent**: Distribution of corner-radius values vs an intended scale.

```bash
# Tailwind:
for r in rounded-sm rounded-md rounded-lg rounded-xl rounded-2xl rounded-full; do \
  n=$(grep -rohE "$r\b" --include="*.tsx" app/ | wc -l); echo "$r  $n"; done

# Inline-style:
grep -oE 'borderRadius:\s*[0-9"%]+' "$LARGEST" | sort | uniq -c | sort -rn | head -15

# CSS files (any stack):
grep -rohE 'border-radius:\s*[0-9.]+(px|rem|em|%)' --include="*.css" --include="*.scss" src/ | sort | uniq -c | sort -rn

# RN StyleSheet:
grep -roE 'borderRadius:\s*[0-9]+' --include="*.tsx" src/ | sort | uniq -c | sort -rn

# Flutter:
grep -rnE 'BorderRadius\.circular\([0-9.]+\)' --include="*.dart" lib/ | sort | uniq -c | sort -rn
```

---

#### A07 · Responsiveness · grids

**Intent**: Adaptive layouts at viewport boundaries.

```bash
# Tailwind — mobile-first column counts + breakpoint distribution:
grep -rohE 'grid-cols-[0-9]+ (sm|md|lg|xl):grid-cols-[0-9]+' --include="*.tsx" app/ | sort | uniq -c
grep -rohE '\b(sm|md|lg|xl|2xl):' --include="*.tsx" app/ | sort | uniq -c

# Inline-style / vanilla-css — @media coverage:
grep -rcE '@media' --include="*.css" --include="*.tsx" --include="*.js" "$ROOT"
grep -rcE 'matchMedia|window\.innerWidth' --include="*.tsx" --include="*.js" "$ROOT"
# 0 @media on a web app = Major.

# RN — adaptive hooks:
grep -rnE 'useWindowDimensions|Dimensions\.get' --include="*.tsx" src/

# Flutter:
grep -rnE 'MediaQuery\.of\(context\)\.size' --include="*.dart" lib/
```

---

#### A08 · Accessibility

**Intent**: Assistive-tech coverage on icon-only controls, semantic headings, reduced-motion gate.

```bash
# Web (any styling):
for needle in 'aria-label' 'aria-describedby' 'aria-hidden' 'role=' 'sr-only' ' alt=' 'tabIndex'; do
  n=$(grep -rln "$needle" --include="*.tsx" --include="*.vue" --include="*.svelte" "$ROOT" 2>/dev/null | wc -l)
  echo "$needle  $n files"
done
# Reduced-motion gate:
grep -rln 'prefers-reduced-motion' --include="*.css" --include="*.scss" --include="*.tsx" "$ROOT"

# RN:
grep -rcE 'accessibilityLabel|accessibilityRole|accessibilityHint' --include="*.tsx" src/
grep -rnE 'AccessibilityInfo\.isReduceMotionEnabled' --include="*.tsx" src/

# Flutter:
grep -rcE '\bSemantics\(' --include="*.dart" lib/
grep -rnE 'MediaQuery\.of\(context\)\.disableAnimations' --include="*.dart" lib/

# SwiftUI:
grep -rcE '\.accessibilityLabel|\.accessibilityHint' --include="*.swift" .
```

---

#### A09 · Motion

**Intent**: Animation count + reduced-motion gate.

```bash
# Tailwind:
for a in animate-spin animate-pulse animate-bounce transition-colors; do
  n=$(grep -roE "$a" --include="*.tsx" app/ | wc -l); echo "$a  $n"; done

# Inline-style / CSS:
grep -rcE 'transition:|animation:|@keyframes' --include="*.css" --include="*.tsx" --include="*.js" "$ROOT"
grep -rln 'prefers-reduced-motion' --include="*.css" --include="*.scss" "$ROOT"

# RN — Animated API:
grep -rcE 'Animated\.(timing|spring|sequence|parallel)' --include="*.tsx" src/

# Flutter — AnimationController:
grep -rcE 'AnimationController|AnimatedBuilder|TweenAnimationBuilder' --include="*.dart" lib/
```

---

#### A10 · Forms

**Intent**: Input/Select/Switch/Label primitive adoption + label association.

```bash
# Tailwind + custom-ui:
grep -rln 'from "@/components/ui/(input|select|switch|label)"' --include="*.tsx" src/
grep -rcE '<input\s+type=' --include="*.tsx" src/   # bypass

# Inline-style — raw <input> count + <label htmlFor> presence:
grep -cE '<input\b' "$LARGEST"
grep -cE 'htmlFor=' "$LARGEST"

# Vue SFC:
grep -rcE '<input\s' --include="*.vue" src/
grep -rln "from ['\"].*ui/Input" --include="*.vue" src/

# RN:
grep -rcE '<TextInput\b' --include="*.tsx" src/
grep -rcE '<Input\b' --include="*.tsx" src/   # adoption signal

# Flutter:
grep -rcE 'TextField\(|TextFormField\(' --include="*.dart" lib/
```

---

#### A11 · Data display

**Intent**: Numeric-column alignment, shared formatter modules.

```bash
# Tailwind:
grep -rln 'tabular-nums' --include="*.tsx" src/ | wc -l

# Inline-style:
grep -rln 'tabular-nums\|fontVariantNumeric' --include="*.tsx" --include="*.js" "$ROOT" | wc -l

# fmt-helper duplication (any JS/TS stack):
grep -rnE '^\s*(const|function)\s+(fmt|format)[A-Z]' --include="*.tsx" --include="*.ts" --include="*.js" "$ROOT" | head -20

# RN:
grep -rcE 'fontVariant.*tabular' --include="*.tsx" src/

# Flutter:
grep -rcE 'FontFeature\.tabularFigures' --include="*.dart" lib/
```

---

#### A12 · Dark / theme mode

**Intent**: How well theme variants are covered.

```bash
# Tailwind — dark: pair ratio:
total=$(grep -roE 'bg-(red|green|amber|blue|purple|orange|emerald|violet|slate)-[0-9]+' --include="*.tsx" app/ | wc -l)
dark=$(grep -roE 'dark:bg-(red|green|amber|blue|purple|orange|emerald|violet|slate)-[0-9]+' --include="*.tsx" app/ | wc -l)
echo "light-only ratio: $((total - dark)) / $total"

# CSS-vars — palettes that flip on data-theme:
grep -rnE ':root\[data-theme=' --include="*.css" "$ROOT"

# Theme-object (inline-style / styled-components):
# Look for the THEMES/themes/theme const and inspect how many variants it defines.
grep -nE '(const|export const)\s+(THEMES|themes|theme)\s*=' "$LARGEST"
grep -cE 'T\.isDark|theme\.isDark' "$LARGEST"   # branch points

# RN:
grep -rcE 'useColorScheme' --include="*.tsx" src/

# Flutter:
grep -rcE 'ThemeMode\.|Brightness\.' --include="*.dart" lib/
```

---

#### A13 · Hygiene

**Intent**: residue, type-escape hatches, stale TODOs.

```bash
# JS/TS:
for n in TODO FIXME XXX 'console\.warn' 'console\.log\b' 'as any' 'as unknown as'; do
  c=$(grep -rn "$n" --include="*.tsx" --include="*.ts" --include="*.js" --include="*.vue" --include="*.svelte" "$ROOT" | wc -l)
  echo "$n  $c"
done

# Flutter:
grep -rcE 'print\(|debugPrint\(' --include="*.dart" lib/

# Android (Kotlin):
grep -rcE 'Log\.[dvwie]\(' --include="*.kt" .

# Swift:
grep -rcE 'print\(' --include="*.swift" .
```

---

#### A14 · Responsiveness · tables (or lists)

**Intent**: Tables on mobile — overflow strategy, column-hiding; or list adaptivity on RN/Flutter.

```bash
# Web (any styling):
grep -rln "<table\b\|<Table\b" --include="*.tsx" --include="*.vue" src/ | while read f; do
  ov=$(grep -c "overflow-x\|overflow:" "$f")
  tb=$(grep -c "<table\b\|<Table\b" "$f")
  echo "$tb tables · $ov overflow · $f"
done
# Tailwind column-hiding strategy:
grep -rohE '(sm|md|lg):(hidden|table-cell|inline|block)' --include="*.tsx" src/ | sort | uniq -c

# RN — FlatList / SectionList configurations:
grep -rcE '<FlatList\b|<SectionList\b' --include="*.tsx" src/
grep -rcE 'horizontal:\s*true' --include="*.tsx" src/

# Flutter:
grep -rcE 'ListView\.builder|GridView\.builder|DataTable\(' --include="*.dart" lib/
```

---

### Step 2b · Read the suspects (mandatory)

Greps tell you the *volume* of drift. They don't tell you *which named component* is broken, whether a primitive is **defined but never called**, whether `className="wz-skeleton"` resolves to a CSS rule that doesn't exist, or whether a second `THEMES` constant lives in an `ErrorBoundary` fallback. **That requires opening files and reading them.**

For each axis where greps surfaced a non-trivial count, open the top 1–2 suspect files (and the canonical primitive's own definition file when relevant). For inline-style monoliths, jump into the largest file at the regions the greps matched and read ±50 lines of context. The deliverable per non-OK axis is a **named-component finding** — a specific component, function, or line range, not just an aggregate count.

**The "named-component finding" rule.** When an axis is Major or Significant, the catalog's *Headline finding* and the per-axis card's *Evidence* must reference at least one named component / function / line range. *"35 files have raw hex"* without a named diagnosis is Minor, not Significant. If you can't name a specific drift site, drop the severity or change your status.

**Smoking guns to look for** (stack-agnostic — translate to the audited stack's idioms; not all will apply to every project):

1. **Broken class / token references.** A `className=` / `style={ x }` that names something *undefined elsewhere*. Cross-reference the class or token name against the global CSS / theme module; if absent, the primitive renders as 0 visible pixels and the supposed "adoption count" is fiction.
   - Recipe: pick the primitive's CSS class from its source (`grep "className=" Skeleton.tsx`), then grep the whole tree for a matching CSS rule (`grep -r "\.wz-skeleton" --include="*.css"`). 0 hits → broken.
2. **Defined-but-unused primitives.** A component / hook / modal declared and exported but never imported anywhere. The audit reads as "primitive exists" but call sites bypass it because it doesn't actually work.
   - Recipe: for each primitive in the UI directory, `grep -rln "from .*/Component" --include="*.tsx" --include="*.vue" | wc -l`. 0 = unused.
3. **Parallel theme / token systems.** A second `THEMES`-like constant declared *outside* the canonical theme module — e.g. `WIZI_THEMES`, `MOBILE_THEMES`, `LEGACY_PALETTE`, `EMBED_COLORS`. Indicates the design system was forked rather than extended for a subtree (chat assistant, embed mode, marketing pages, mobile).
   - Recipe: `grep -rnE "(const|export const)\s+[A-Z_]+_?THEMES?\s*=" --include="*.{ts,tsx,js,jsx}" src/`
4. **Inlined copies of canonical constants.** A hand-typed `const T = { accent: "#xxx", text: "#xxx", … }` sitting in an `ErrorBoundary`, fallback path, test fixture, or pre-React-mount bootstrap. Silently drifts the day the canonical changes.
   - Recipe: grep for hex literal patterns near the names of canonical token keys (e.g. `accent:`, `surface:`, `card:`) and check whether they're inside `THEMES` itself or somewhere else.
5. **Multiple ternaries reimplementing the same lookup.** Five different `(s === "critical" ? "..." : s === "high" ? "..." : ...)` blocks across files where a shared `SEVERITY_TOKENS` map should exist. Each tends to drift slightly.
   - Recipe: `grep -rnE '\?\s*"[^"]*"\s*:\s*[^?]+\?\s*"[^"]*"\s*:' --include="*.tsx" src/ | wc -l` (ternary nesting count, sample and read).
6. **Native browser dialogs bypassing custom modals.** `window.confirm`, `window.alert`, `window.prompt` in a codebase that defines `<ConfirmModal>` / `<AlertModal>`.
   - Recipe: `grep -rnE 'window\.(confirm|alert|prompt)\(' --include="*.{ts,tsx,js,jsx}" src/`
7. **Hex case duplicates.** Same color used in both upper- and lower-case form (`#F59E0B` and `#f59e0b` appearing as separate sort buckets) — format jitter, not intent. Compare the as-typed distinct count to the case-normalised distinct count.
8. **Numeric scale jitter.** `borderRadius: 5/6/7/8/9/10` for the same logical "small surface", or `fontSize: 10/10.5/11/12/12.5/13` for body text. **Non-integer values (10.5, 12.5) are an especially loud smoking gun** — nobody designs a system around 10.5px on purpose.
9. **Format jitter on the same property.** `letterSpacing` written as `.05em` / `0.05em` / `.06em` / `0.06em` for the same visual intent; `padding: "6px 12px"` vs `padding: 6 12` vs `paddingX: 12; paddingY: 6` for the same control.
10. **Component-name shadowing.** A `<Button>` declared in `pages/Foo.tsx` *as well as* `components/ui/Button.tsx`, and they don't agree. Same for `<Card>`, `<Modal>`, `<Section>`. Greppable as `grep -rnE '^(const|function)\s+(Btn|Button|Card|Section|Modal)\b'`.
11. **Per-file fmt helpers.** `const formatPercent = …` reimplemented across 3+ files instead of imported from a shared lib. Each has a slightly different rounding rule.
12. **Icon-only controls without label.** `<button>` containing only `<Icon/>`, no `aria-label`. Greppable via context lines on `<Loader2|X|ChevronDown|Trash|Plus`.
13. **Animation without motion gate.** Every `transition:` / `animation:` site, and no file mentions `prefers-reduced-motion`. The greps in A09 surface this; reading suspects confirms whether a wrapper hook exists.
14. **Stale escape hatches with rotten reasons.** `as any` with a `// FIXME: remove after v3` comment from 18 months ago; `@ts-ignore` clusters that survived the package upgrade they were waiting on.

When suspects don't reveal a named finding, **lower the severity** for that axis. The catalog's Volume column is what greps produce; the Headline finding column is what reading produces.

This step typically takes longer than the greps. Don't skip it — the named-component findings are what make the audit actionable.

### Step 3 · Capture snapshots (optional, for tracking progress)

```bash
~/.claude/skills/style-drift/scripts/snapshot.py <root> --out .style-drift/before.json
# (apply fixes)
~/.claude/skills/style-drift/scripts/snapshot.py <root> --out .style-drift/after.json
~/.claude/skills/style-drift/scripts/compare.py .style-drift/before.json .style-drift/after.json --pdf docs/style-drift-report.pdf
```

`snapshot.py` was written against Tailwind class patterns and currently captures ~5 axes; for non-Tailwind stacks, capture per-axis counts directly via the Step 2 recipes or extend `snapshot.py`.

### Step 4 · Interpret + categorise per axis

For each axis, decide a status using the rules below — but **apply the Step-0 recon-driven status adjustments first**, and apply the **named-finding requirement** from Step 2b: an axis can only be Major/Significant if Step 2b found a specific drift site worth naming. Otherwise drop to Minor.

- 🔴 **Major** — primitive/pattern doesn't exist at the project level and many call sites reimplement it; OR a semantic / a11y violation affects the whole app
- 🟠 **Significant** — primitive exists but ~30%+ of call sites bypass it; OR a token gap forces frequent overrides
- 🟡 **Minor** — cosmetic, isolated; one sweep fixes it
- 🟢 **OK** — the codebase gets this right (call this out — inverse signals matter)
- 🟢 **OK · N/A** — axis doesn't apply to this stack (e.g. A02 on an inline-style project with no variant API)

### Step 5 · Build the axis catalog table

Lead the report with one table. **Always 14 rows — no exceptions.** Every axis A01–A14 must appear in the catalog, in order, even if an axis doesn't apply to this stack (render as `OK · N/A` with one-line justification). Don't drop, merge, or rename axes; the spine of the report is the catalog itself, and a missing row tells the reader nothing was checked.

The **Headline finding** column must reference a named component / function / line range when status is Major or Significant. Aggregate-only descriptions ("35 files have raw hex") indicate the read-the-suspects step (Step 2b) was skipped — go back and do it.

```
| Axis | Name                       | Status      | Headline finding                                | Volume                          |
| A01  | Primitives                 | Significant | <Btn>:296 vs raw <button>:281                   | Btn:296 · Badge:73 · Card:58    |
| A02  | Library convention         | OK · N/A    | No shadcn/Radix/MUI — inline-style stack        | —                               |
| A03  | Application convention     | Major       | 111 components in one 31,715-line file          | 1 file · 111 funcs              |
| …    | …                          | …           | …                                               | …                               |
```

### Step 6 · Generate the visual preview HTML — REQUIRED

The preview file at `<root>/style-drift-preview.html` must contain:

1. **Doc header** — title, root path, **recon pills** (stack, framework, styling, tokens, tree, primitives — verbatim from recon JSON), KPI chip row (1 chip per Major/Significant axis)
2. **Axis catalog** — the same table from Step 5, rendered as HTML
3. **Legend** — red dot = drift in BEFORE, green dot = resolved in AFTER
4. **Section 1 · Axes in detail** — one `axis-card` per axis (14 cards minimum). Each card:
   - Numbered header (A01, A02, …) + axis name + status pill + scope line
   - Evidence block: for Major/Significant axes, **at least one named-component finding** (component / function name + line range), plus the supporting aggregate counts. Pure-count evidence (no named site) means the read-the-suspects step was skipped — fix the audit, not the card.
   - File:line citations must point to real code paths from the audited tree, in the audit's actual syntax (don't paste Tailwind className examples in an inline-style audit).
   - BEFORE / AFTER side-by-side — small live demo + code snippet **in the syntax of the audited stack**, mirroring the named-component finding when possible (don't draw a generic chip if the finding is "`RootCauseChainBanner` ignores its `T` prop" — render that banner).
   - Footer with `Δ` (codebase-wide delta the fix produces)
   - For OK / OK · N/A axes, render a single explanatory panel instead of a BEFORE/AFTER pair. Multiple OK axes may be batched into one card to save space, but each axis's status pill must still appear somewhere visible.
5. **Section 2 · Page (or screen) in context** — full BEFORE/AFTER mock of the worst-drift page/screen, with `A0N` notes above each drifty section so the reader can trace each visual change back to its axis
6. **Footer note** — summary, file path

Save to `<root>/style-drift-preview.html`. **Tell the user it's been written, that no code has been edited, and ask them to confirm before fixes are applied.**

Do **not** apply any edits until the user explicitly confirms after seeing the preview. This is a non-negotiable safety gate.

#### Picking the page for Section 2

- Pick the single page / screen / route with the highest **drift density** — count drift hits per 100 lines, not per file.
- For monoliths (single file): pick the *region* with the highest density (e.g. one tab/view within the file). Label it by region name rather than file path.
- For RN/Flutter: pick a screen, not a component.
- One page is enough. If two pages tie and surface visually different drift (chart-heavy vs form-heavy), include both as separate BEFORE/AFTER blocks in the same HTML file.
- Render on the **theme that exposes the most drift** — usually Dark, if any drift involves hardcoded light-only palettes.

#### Layout rules (don't skip)

1. Stack panels vertically by default; side-by-side only at `min-width: 1700px`.
2. Every grid `1fr` column ⇒ `minmax(0, 1fr)`.
3. `min-width: 0` on flex/grid children + `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` on long-text cells.
4. Match emoji line-height to lucide / icon SVG sizing.
5. No `position: absolute` overlays — render modals/assistants as inline panels in the right dock.
6. `flex-wrap: wrap` on toolbar action rows.

#### Axis-card structure (Section 1)

```html
<div class="axis-card">
  <div class="head">
    <span class="num">A07</span>
    <span class="axis-name">Responsiveness · grids</span>
    <span class="status significant">Significant</span>
    <span class="scope">file:line scope · key counts</span>
  </div>
  <div class="evidence">
    <span class="lbl">Pattern</span>
    <div>…the evidence that justifies the status…</div>
  </div>
  <div class="pair">
    <div class="b"><div class="tag"><span class="dot"></span>Before</div>
      <div class="demo surface"><!-- rendered BEFORE state --></div>
      <div class="code">code that produced the BEFORE — in the audited stack's syntax</div>
    </div>
    <div class="a"><div class="tag"><span class="dot"></span>After</div>
      <div class="demo surface"><!-- rendered AFTER state --></div>
      <div class="code">code/primitive that produces the AFTER</div>
    </div>
  </div>
  <div class="footer"><span class="delta">−N inline strings · +1 primitive</span></div>
</div>
```

For OK / OK · N/A axes, replace the `pair` with `<div class="single">` containing a short explanation.

#### Status pill colors

```css
.status.major       { background: #FEF2F2; color: #B91C1C; }
.status.significant { background: #FFF7ED; color: #C2410C; }
.status.minor       { background: #FFFBEB; color: #B45309; }
.status.ok          { background: #F0FDF4; color: #16A34A; }
```

#### Scaffold

`scripts/preview-template.html` is a minimal 3-column app-frame skeleton. Copy to repo root, then build out Sections 1 (axis cards) and 2 (page in context). The scaffold's split / surface / note classes are reusable; add axis-card / status-pill classes on top.

### Step 7 · Offer to execute (after user confirms)

Order of operations once approved (adapted to recon):

1. **Tree shape first** if `tree: single-file-monolith` or `few-large-files` — split the file. Every other axis becomes easier once components are file-scoped.
2. **Toolkit gaps** (A02) when the stack has a variant API. Extending an enum unblocks downstream overrides.
3. **Primitive extraction** (A01, A03). Promote inline duplicates; add missing chrome primitives (PageHeader, Breadcrumb, Pagination, useQueryFilters).
4. **Mechanical codemods** (A04, A05, A06). Hex→token, h1 jitter → PageTitle, eyebrow → Eyebrow primitive, bare radius audit. Sed/grep can do most.
5. **Per-page migrations** (A07, A12, A14). Mobile-first grids · theme-pair fills · table responsive strategy.
6. **A11y + motion sweep** (A08, A09). aria coverage on icon buttons · reduced-motion gate.
7. **Hygiene** (A13). residue, TODO triage.

### Step 8 · Verify clean state

After fixes land:

```bash
# Re-run recon — confirm tree/primitives values changed as expected.
~/.claude/skills/style-drift/scripts/recon.sh <root>

# Type-check / build (whatever the project uses):
npx tsc --noEmit          # TS-based
npm run build             # web
flutter analyze           # Flutter
xcodebuild -quiet         # iOS

# Re-run any axis recipes that drove the original ranking.
```

The catalog should now show every axis at Minor or OK / OK · N/A.

## Reporting format

Output structure (in the chat reply):

```
## UI audit — <project> across 14 axes

[Short overall summary — 1 paragraph. Mention recon findings: stack, styling, tree shape.]

### Axis catalog

[the 14-row table — including OK · N/A rows]

### Highest-leverage fixes

1. <axis with the most downstream impact — usually a tree-shape fix on monoliths, or a toolkit gap on standard trees>
2. …

[Visual preview is at `style-drift-preview.html`. Open in a browser…
 No code edited yet — confirm to proceed.]
```

Don't dump every file:line in chat — the catalog table is the spine and the HTML is the detail. The chat reply summarises and points to the preview.

## Notes

- This skill is **read-only by default**. Audit + preview HTML are the deliverables; edits only happen after user confirmation.
- **Recon is mandatory.** Skipping recon and assuming Tailwind+React leads to misleading audits (zero hits everywhere when the project is, say, inline-style or Vue SFC). If recon returns `unknown`, ask the user — don't guess.
- **Visual preview is mandatory** — drift refactors touch dozens of files and the user benefits from seeing the visual delta before approving.
- **Code snippets in the preview must match the audited stack's syntax.** Showing Tailwind `className=` examples for a Vue SFC project (or vice versa) breaks the user's trust in the audit.
- **Pair with `extract-toolkit`.** If `docs/ui-toolkit.json` is missing, suggest running `extract-toolkit` first — the audit is more grounded with a project-specific canonical reference than with bundled defaults. The 14 axes apply with or without a toolkit JSON.
- If the user names a specific axis ("audit responsiveness", "scan dark mode coverage"), run only that axis's recipes and produce a focused report — but always include the full axis catalog so the user can see what was skipped.
- The Markdown view of the toolkit (`docs/ui-toolkit.md`) is human-readable but isn't machine-parsed — always pass the JSON. The PDF is never read by this skill.
- For stacks the recipes table doesn't cover (Compose UI, SwiftUI native, Qt, GTK, Lit, Solid SSR, …), translate the *intent* of each axis to the stack's idioms and ask the user to validate the recipes before relying on them.

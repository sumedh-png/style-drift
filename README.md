# style-drift

A [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code/skills) that audits any frontend codebase for design-system drift across 14 UX axes (color tokens, typography, radii, primitives, spacing, accessibility, dark mode, responsiveness, motion, forms, data display, and more).

Stack-agnostic — adapts to React / Vue / Svelte / Angular / Solid / React Native / Flutter / SwiftUI / Compose with Tailwind, CSS Modules, styled-components/emotion, inline styles, or vanilla CSS. A reconnaissance step detects the stack and styling system, then the audit runs only the recipes that match.

Returns an axis catalog (Major / Significant / Minor / OK) plus a self-contained visual-preview HTML with per-axis BEFORE/AFTER comparisons. Edits are only applied after the user reviews the preview.

## Install

The skill must live at `~/.claude/skills/style-drift/` for Claude Code to discover it:

```bash
git clone https://github.com/Intentwise/style-drift.git ~/.claude/skills/style-drift
```

To update later:

```bash
git -C ~/.claude/skills/style-drift pull
```

## Use

Inside Claude Code, invoke with the slash command:

```
/style-drift
```

Or trigger by intent — phrasings like "audit the UI", "find style deviations", "scan for design drift", or "check inconsistencies with the toolkit" will fire the skill automatically.

## What's in the box

| File | Purpose |
|------|---------|
| [SKILL.md](SKILL.md) | Full skill instructions — 14 axes, per-stack recipes, output format |
| [scripts/recon.sh](scripts/recon.sh) | Detect stack, styling system, token shape, primitive library |
| [scripts/scan.sh](scripts/scan.sh) | Tailwind utility-class drift scan |
| [scripts/snapshot.py](scripts/snapshot.py) | Take page/component snapshots for BEFORE/AFTER |
| [scripts/compare.py](scripts/compare.py) | Render the visual-preview HTML |
| [scripts/toolkit_info.py](scripts/toolkit_info.py) | Read a toolkit JSON reference |
| [scripts/preview-template.html](scripts/preview-template.html) | HTML template for the report |

## When NOT to use

- ESLint / Prettier formatting issues — different toolchain
- Runtime visual regression — use Chromatic, Percy, or screenshot-diffing tools
- One-off "what does this component look like?" — that's a Read, not an audit

## License

Internal Intentwise tooling.

# Professional Ops Full UI Overhaul Design

## Context
The current TUI visual language is a purple-centered card style. The goal is a full visual-system overhaul that feels like a professional operations console: structured, dense, and readable, with restrained accents and consistent panel grammar across onboarding and core app screens.

## Goals
- Replace the current global visual identity with a neutral professional-ops theme.
- Apply one coherent layout grammar across onboarding and all main TUI screens.
- Preserve workflows and keybindings while improving hierarchy, status visibility, and readability.
- Keep Textual responsiveness and async safety unchanged.

## Non-Goals
- No feature behavior rewrites unless required by new composition.
- No introduction of time-based event sequencing hacks.
- No large architecture changes outside presentation/theme layers.

## Visual Direction
### Palette and Tone
- Base: charcoal/slate surfaces.
- Accent: restrained cyan/green/amber semantic signals.
- No purple-first branding.
- High contrast for labels/statuses, muted body text.

### Typography and Density
- Dense, data-forward rows for metadata and status.
- Explicit section labels and panel headers.
- Consistent spacing scale to avoid random padding/margins.

### Panel Language
Shared primitives used everywhere:
- `panel`: framed region with title and optional status chip.
- `section-title`: uppercase, low-noise heading with divider.
- `value-row`: compact label/value display.
- `status-chip`: IDLE/OK/WARN/ERR visual states.
- `keyhint-line`: concise keyboard guidance.

## Architecture
### Global Theme Tokens
`flow/tui/common/theme.tcss` becomes the single source for:
- Color tokens: surfaces, borders, text hierarchy, semantic statuses.
- Spacing tokens and border styles.
- Baseline styling for Header/Footer, OptionList/ListView/Input/Button, Markdown, Toast.

### App-Wide Shell Pattern
Screens align to a dashboard shell:
- Top bar: title/context and status indicators.
- Main region: one or more framed panels.
- Context panel: details/help/selection metadata (right or bottom depending on screen).
- Bottom strip: key hints and current mode signals.

## Screen Composition Changes
### Onboarding
Targets:
- `provider`
- `resource_storage`
- `credentials`
- `validation`
- `first_capture`

Changes:
- Shift from centered card to split operational layout.
- Add progress + section context line.
- Keep existing navigation flow and validation behavior.

### Main TUI
Targets:
- `inbox`
- `projects`
- `action`
- `review`
- `process`
- `focus`

Changes:
- Apply consistent panel scaffold and section header grammar.
- Promote state visibility (selection, filter mode, queue/context depth, execution state).
- Keep current shortcuts and focus behavior contract.

### Dialogs and Shared Widgets
Targets:
- `defer_dialog`
- `process_task_dialog`
- `project_picker_dialog`
- shared card/sidecar widgets

Changes:
- Match panel borders, spacing rhythm, and status/keyhint semantics.

## Motion and Interaction
- Keep interactions deterministic and unchanged by default.
- Use subtle visual emphasis for focus/selection transitions.
- Avoid flashy or heavy animations; prioritize clarity and stability.

## Risks and Mitigations
- Risk: visual regressions in narrow terminals.
  - Mitigation: manual narrow-width checks and targeted TCSS constraints.
- Risk: inconsistency between screen-local styles and global tokens.
  - Mitigation: remove duplicate token declarations from local TCSS and centralize in global theme.
- Risk: accidental keybinding/flow changes during layout refactor.
  - Mitigation: keep Python event/binding logic stable and run binding-focused tests.

## Verification Strategy
- Run targeted unit tests for onboarding + affected screens.
- Run full `pytest tests/unit -v` after integration.
- Manual checks:
  - standard and narrow terminal widths
  - empty/error states
  - focus traversal and shortcut visibility
  - readability/contrast across semantic states

## Rollout Notes
- Implement in phased commits:
  1. Global tokens and common widgets
  2. Onboarding screens
  3. Main screens and dialogs
  4. Test/doc updates and verification

# Module Mockups — Pedal Widget Spec

Design reference and layout spec for the six global module "pedals" in the Signal
Chain UI. These are design references and the implementation spec — the PyQt6
widgets are built FROM this spec; they do not load the SVG/PNG at runtime.

Single source of truth for module visual design: if the design changes, update
`pedal_all_six.svg` and this spec together.

## Files
- `pedal_all_six.svg` — master reference, all six pedals (authoritative)
- `pedal_reference.png` — rendered PNG, for quick viewing

## Grid & scaling
Everything is built on one base unit `u`; the whole widget scales by changing `u` alone.
- Base: `u = 8px`
- Implementation: derive `u = widget_width / 16` on layout, then place every child in
  multiples of `u`. The pedal then scales fluidly at any size with no hard-coded pixels.
- Fonts scale with `u` (sizes below are in `u`).

## Enclosure (one pedal)
- Size: 16u × 32u (128 × 256px at base) — a 1:2 stompbox ratio
- Corner radius: 1.5u
- Vertical layout: 1u top margin · 16u config plate · 14u body · 1u bottom margin
- Colors (per module, table below): enclosure = Body · recessed plate = Plate ·
  LED/handles/title = Accent

## Config plate (top, recessed panel)
- Inset 1u from enclosure sides → 14u wide × 16u tall; internal padding 1u
- Contents, top → bottom:
  - Header (2u): status LED (1u circle, Accent, left) · title (1.25u uppercase bold,
    Accent) · GLOBAL badge (0.75u uppercase, muted, right)
  - 3 slider rows (2.5u each): label (1u uppercase, left) · track (2px line, ~1u Accent
    handle, center) · value (1u, right-aligned)
  - OUTPUT/INPUT row (1.5u): "← OUTPUT" left · "INPUT →" right (0.75u, muted)

## Body (bottom)
- 16u × 14u
- Contents, top → bottom:
  - Full module name (1u, centered)
  - ON footswitch: rounded-rect (1u radius), ~12u × 5u, centered; "ON" large (2u)
  - SIGNAL-CHAIN footer (0.75u, uppercase, letter-spaced, muted, bottom-centered)

## Module spec
| Module | Title | Controls (label / default) | Body | Plate | Accent |
|--------|-------|----------------------------|------|-------|--------|
| Conversation History | CONV. HISTORY | DEPTH 10 / WINDOW 20 / TOKENS 4096 | #1a3a5c | #0c1e36 | #7ab8e8 |
| Connected Accounts | CONNECTED | TOKEN 80 / SCOPE 3 / EXPIRE 7 | #3a1a1a | #1e0808 | #e88a8a |
| Markdown Output | MARKDOWN | FORMAT 2 / LEVEL 75 / WRAP 80 | #2a2800 | #141200 | #e0d800 |
| Web Access | WEB ACCESS | TIMEOUT 10 / DEPTH 2 / CACHE 50 | #1a3020 | #0a1a10 | #4ab880 |
| File Access | FILE ACCESS | MAX SIZE 10 / DEPTH 3 / WATCH 0 | #1a2a3a | #0a1820 | #4a8ab0 |
| Clock | CLOCK | ZONE 0 / FORMAT 0 / INTERVAL 5 | #2a1a3a | #1a0a28 | #8a4ab0 |

Shared elements on every pedal: GLOBAL badge, status LED, title, three sliders with
readouts, OUTPUT/INPUT row, full-name label, ON footswitch, SIGNAL-CHAIN footer.

## Source & regeneration
Generated with Gemini as a specialist design pass. To revise: regenerate the master
SVG, re-export the PNG, and update this spec to match. Keep all three consistent.
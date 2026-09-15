# Design system

Applies to every tool in this project. Colours and typography come from mistral.ai. Off limits: their logo and product names. Warm colours only. Colour values below were read from mistral.ai's stylesheet on 15 September 2026; the status colours and everything from Typography down are ours.

Rules that hold everywhere: no shadows, no gradients in the interface, 1 px borders, weight 400 only, everything readable at 1280 px.

## Tokens

```css
:root {
  --font-display: "Instrument Serif", Georgia, serif; /* free stand-in for their commercial ALT Mistral */
  --font-ui: "Inter", system-ui, sans-serif;          /* weight 400 only; hierarchy by size, not weight */
  --font-code: ui-monospace, "SF Mono", Menlo, monospace;

  --color-text: #18181b;          /* not pure black */
  --color-text-muted: #56566c;
  --color-bg: #fbfbf8;            /* page background */
  --color-surface: #f5f4ef;       /* cards, panels */
  --color-surface-hover: #ebe9e0; /* hovered rows and menu items */
  --color-border: #e4e3de;        /* 1 px borders */
  --color-accent: #fa500f;        /* actions and active states only */
  --color-accent-2: #ff8204;      /* secondary accent, sparingly */
  --color-accent-3: #fec63a;      /* secondary accent, sparingly */

  --color-success: #5c6b1f;       --color-success-bg: #f0f1dc;
  --color-warning: #8a5e00;       --color-warning-bg: #fff4d2;
  --color-error:   #b31200;       --color-error-bg:   #ffdccf;

  --radius-button: 8px;
  --radius-card: 12px;
}
```

## Colours

| Token | Used for | Not used for |
|---|---|---|
| `--color-text` | All body text, headings, button labels on accent fills | Borders, icons that carry state |
| `--color-text-muted` | Secondary text: timestamps, captions, helper text, placeholder | Anything the user must read to act |
| `--color-bg` | Page background only | Cards, inputs |
| `--color-surface` | Cards, panels, table header, input background, disabled fills | Page background, hover states |
| `--color-surface-hover` | Hovered table rows and menu items | Anything static |
| `--color-border` | Every border and divider | Text |
| `--color-accent` | Primary button fill, active tab underline, focus ring, active menu item marker, selected row marker, links | Text at body size, large fills, decoration, headings |
| `--color-accent-2` | One highlighted value per page at most, for example a current temperature, and the loading indicator | Buttons, borders, text under 20 px |
| `--color-accent-3` | Badges for informational counts | Buttons, text, borders |
| `--color-success/warning/error` | Icon, left border and badge text for that state | Body text, buttons |
| `--color-*-bg` | Fill behind the icon and badge for that state, and the error message box | Anything without the matching state |

The accent is a marker, not a paint. If a screen has more than one accent-filled element outside the primary button, that is one too many.

Contrast, WCAG 2.1 relative luminance formula, AA requires 4.5:1 for text and 3:1 for large text and UI components:

| Foreground | Background | Ratio | AA |
|---|---|---|---|
| `--color-text` | `--color-bg` | 17.1:1 | pass |
| `--color-text` | `--color-surface` | 16.1:1 | pass |
| `--color-text-muted` | `--color-bg` | 6.9:1 | pass |
| `--color-text-muted` | `--color-surface` | 6.5:1 | pass |
| `--color-text` | `--color-accent` (primary button) | 5.3:1 | pass |
| `--color-success` | `--color-success-bg` | 5.1:1 | pass |
| `--color-warning` | `--color-warning-bg` | 5.2:1 | pass |
| `--color-error` | `--color-error-bg` | 5.5:1 | pass |
| `--color-accent` | `--color-bg` | 3.3:1 | fails for text, passes as UI component |
| white | `--color-accent` | 3.4:1 | fails for text |

Consequences: primary button labels are `--color-text` on accent, never white. The accent is never a text colour except for links, which are underlined so colour is not the only signal.

## Typography

| Style | Font | Size | Line height | Where |
|---|---|---|---|---|
| Display | display serif | 40 px | 48 px | One per page: the tool's name or the answer to the user's question |
| Heading | display serif | 24 px | 32 px | Section and card titles |
| Body | ui | 16 px | 24 px | Everything else, including inputs and buttons |
| Small | ui | 13 px | 20 px | Captions, timestamps, table metadata, helper text, badges |
| Label | ui, uppercase, letter-spacing 0.06em | 12 px | 16 px | Eyebrow above a heading or a column header, rare |
| Code | code | 13 px | 20 px | Tool arguments, raw results, tokens, ids |

The serif is for display and heading only. It is never used for body text, buttons, inputs, tables or anything under 24 px.

Hierarchy is by size and colour, never by weight. Emphasis inside body text uses `--color-text` against `--color-text-muted` surroundings, not bold.

Uppercase labels are in character but rare: at most one per card, never in a sentence, never for a button, and always `--color-text-muted`.

## Spacing

4 px base. Steps: 4, 8, 12, 16, 24, 32, 48, 64.

| Step | Use |
|---|---|
| 4 | Icon to its label, badge padding vertical |
| 8 | Badge padding horizontal, gap between inline items, input padding vertical |
| 12 | Button and input padding horizontal, gap between related controls |
| 16 | Card padding, table cell padding, gap between components in a row |
| 24 | Gap between cards, gap between form rows |
| 32 | Gap between sections inside a page |
| 48 | Page padding top and bottom |
| 64 | Gap between a page's main content and its trace or settings panel |

Max content width 960 px, centred. Page padding 32 px left and right at 1280 px.

## Component styles

All interactive components: `--font-ui` 16 px, height 40 px, focus ring 2 px `--color-accent` with 2 px offset, visible on keyboard focus only. Transitions 120 ms on background and border colour, nothing else animates except the loading indicator.

| Component | Size | Fill | Text | Border | Radius | Hover | Active / selected |
|---|---|---|---|---|---|---|---|
| Button primary | 40 px, padding 0 16 px | `--color-accent` | `--color-text` | none | 8 px | fill `--color-accent-2` | fill darkens 8% |
| Button secondary | 40 px, padding 0 16 px | transparent | `--color-text` | `--color-border` | 8 px | fill `--color-surface` | fill `--color-surface-hover` |
| Button disabled | as above | `--color-surface` | `--color-text-muted` | `--color-border` | 8 px | none | none, cursor not-allowed |
| Text input | 40 px, padding 8 12 px | `--color-surface` | `--color-text`, placeholder muted | `--color-border` | 8 px | border `--color-text-muted` | focus ring, border `--color-accent` |
| Dropdown | as text input, chevron right, 16 px | `--color-surface` | `--color-text` | `--color-border` | 8 px | as text input | open: border `--color-accent`, list is a card with menu items |
| Card | padding 16 px | `--color-surface` | `--color-text` | `--color-border` | 12 px | none | none |
| Table | cell padding 12 16 px | header `--color-surface`, rows `--color-bg` | header small label, cells body | row divider `--color-border` bottom only | 12 px on the outer card | row `--color-surface-hover` | row gets 2 px left border `--color-accent` |
| Menu item | 40 px, padding 0 12 px | transparent | `--color-text` | none | 8 px | `--color-surface-hover` | `--color-surface-hover` plus 2 px left border `--color-accent` |
| Badge | 20 px, padding 0 8 px | state `-bg` token or `--color-accent-3` | small, state token or `--color-text` | none | 999 px | none | none |
| Loading indicator | 16 px circle | 2 px ring, `--color-border` with a `--color-accent-2` arc | none | none | round | none | spins 800 ms linear |
| Error message | padding 12 16 px | `--color-error-bg` | `--color-text`, icon `--color-error` | 2 px left `--color-error` | 8 px | none | none |
| Empty state | card, padding 48 px, centred | `--color-surface` | heading serif 24 px, one body line muted, one secondary button | `--color-border` | 12 px | none | none |

Error messages say what failed and what the user can do, in one sentence each. The loading indicator sits where the result will appear, never in the button.

## Responsive behaviour

Primary target is a 1280 px screen share. Nothing below 768 px matters.

| Width | Content column | Settings or trace panel | Tables | Cards in a row |
|---|---|---|---|---|
| 1280 | 960 px centred, 32 px page padding | Right side, 320 px, content column shrinks to fill | Full | Up to 3 |
| 1024 | Full width minus 24 px padding | Right side, 288 px | Full, small text in secondary columns | Up to 2 |
| 768 | Full width minus 16 px padding | Full screen overlay with a close button, opened from a secondary button | Secondary columns hidden, rows stack label over value | 1 |

Type scale, spacing and component sizes do not change with width. Only columns, panels and padding do.

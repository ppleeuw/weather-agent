# Design system

Applies to every tool in this project. Colours and typography follow mistral.ai. Off limits: their logo and product names. The theme is dark, like their site; the accents are warm. Neutral and accent values below were read from mistral.ai's stylesheet on 16 September 2026 (their dark surfaces, their orange and yellow); the status colours and everything from Typography down are ours.

Rules that hold everywhere: no shadows, no gradients in the interface, 1 px borders, weight 400 only, everything readable at 1280 px.

## Tokens

```css
:root {
  color-scheme: dark;

  --font-display: "Space Grotesk", "Inter", system-ui, sans-serif; /* free stand-in for their commercial ALT Mistral */
  --font-ui: "Inter", system-ui, sans-serif;                         /* weight 400 only; hierarchy by size, not weight */
  --font-code: "Space Mono", ui-monospace, monospace;                /* their mono face, also for labels */

  --color-text: #fafaf4;          /* their text on dark: cream, not pure white */
  --color-text-muted: #a1a1aa;    /* steel 400 */
  --color-bg: #101013;            /* steel 950, page background */
  --color-surface: #1a1a1e;       /* steel 900, cards and panels */
  --color-surface-hover: #27272b; /* steel 800, hovered rows and menu items */
  --color-border: #31313a;        /* their border on dark, 1 px */
  --color-accent: #fa500f;        /* orange, actions and active states only */
  --color-accent-2: #ff8204;      /* secondary accent, sparingly */
  --color-accent-3: #fec63a;      /* yellow, badges for informational counts */
  --color-on-accent: #101013;     /* text on an accent fill */

  --color-success: #94eacc;       --color-success-bg: #0f3b2a;
  --color-warning: #fec63a;       --color-warning-bg: #3a2a05;
  --color-error:   #f66c60;       --color-error-bg:   #4a1208;

  --radius-button: 8px;
  --radius-card: 12px;
}
```

## Colours

| Token | Used for | Not used for |
|---|---|---|
| `--color-text` | All body text, headings, text in the error box | Borders, icons that carry state, labels on accent fills |
| `--color-text-muted` | Secondary text: timestamps, captions, helper text, placeholder, labels | Anything the user must read to act |
| `--color-bg` | Page background and table rows | Cards, inputs |
| `--color-surface` | Cards, panels, table header, input background, disabled fills, the modal | Page background, hover states |
| `--color-surface-hover` | Hovered table rows and menu items | Anything static |
| `--color-border` | Every border and divider, the health dot before its first check | Text |
| `--color-accent` | Primary button fill, active menu item marker, focus ring, selected row marker, links | Body text, large fills, decoration, headings |
| `--color-accent-2` | Primary button hover, the loading indicator arc | Buttons at rest, borders, text |
| `--color-accent-3` | Badges for informational counts, the top rows of the logo | Buttons, body text, borders |
| `--color-on-accent` | Text on the primary button, on a plain badge, the switch knob when on | Anything not on an accent fill |
| `--color-success/warning/error` | Icon, badge text and left border for that state | Body text, buttons |
| `--color-*-bg` | Fill behind a state badge and the error message box | Anything without the matching state |

The accent is a marker, not a paint. If a screen has more than one accent-filled element outside the primary button, that is one too many.

Contrast, WCAG 2.1 relative luminance formula, AA requires 4.5:1 for text and 3:1 for large text and UI components:

| Foreground | Background | Ratio | AA |
|---|---|---|---|
| `--color-text` | `--color-bg` | 18.1:1 | pass |
| `--color-text` | `--color-surface` | 16.6:1 | pass |
| `--color-text` | `--color-surface-hover` | 14.2:1 | pass |
| `--color-text-muted` | `--color-bg` | 7.4:1 | pass |
| `--color-text-muted` | `--color-surface` | 6.8:1 | pass |
| `--color-on-accent` | `--color-accent` (primary button) | 5.6:1 | pass |
| `--color-on-accent` | `--color-accent-2` (hover) | 7.6:1 | pass |
| `--color-accent` | `--color-bg` (links) | 5.6:1 | pass |
| `--color-success` | `--color-success-bg` | 8.9:1 | pass |
| `--color-warning` | `--color-warning-bg` | 8.8:1 | pass |
| `--color-error` | `--color-error-bg` | 5.2:1 | pass |
| `--color-border` | `--color-bg` | 1.5:1 | a divider, not a control |

Consequences: labels on accent fills use `--color-on-accent`, never the light text. The accent is a text colour only for links, which stay underlined so colour is not the only signal.

## Typography

| Style | Font | Size | Line height | Where |
|---|---|---|---|---|
| Display | display | 40 px | 48 px | One per page: the tool's name or the answer to the user's question |
| Heading | display | 24 px | 32 px | Section and card titles |
| Body | ui | 16 px | 24 px | Everything else, including inputs and buttons |
| Small | ui | 13 px | 20 px | Captions, timestamps, table metadata, helper text, badges |
| Label | code, uppercase, letter-spacing 0.06em | 12 px | 16 px | Eyebrow above a heading, column headers, section titles inside a card |
| Code | code | 13 px | 20 px | Tool arguments, raw results, tokens, ids |

The display face is for display and heading only. It is never used for body text, buttons, inputs, tables or anything under 24 px. The mono face carries labels and code, as on mistral.ai.

Hierarchy is by size and colour, never by weight. Emphasis inside body text uses `--color-text` against `--color-text-muted` surroundings, not bold.

Uppercase labels are in character: one per card as a title, column headers, never in a sentence, never for a button, and always `--color-text-muted`.

## Spacing

4 px base. Steps: 4, 8, 12, 16, 24, 32, 48, 64.

| Step | Use |
|---|---|
| 4 | Icon to its label, badge padding vertical, rows in the health card |
| 8 | Badge padding horizontal, gap between inline items, input padding vertical, the `.stack` and `.row` utilities |
| 12 | Button and input padding horizontal, gap between related controls |
| 16 | Card padding, table cell padding, gap between components in a row |
| 24 | Gap between cards, gap between form rows |
| 32 | Gap between sections inside a page |
| 48 | Page padding top and bottom |
| 64 | Gap between a page's main content and its settings window |

Max content width 960 px, centred. Page padding 32 px left and right at 1280 px.

Two utilities for blocks that scripts build: `.stack` is a column with an 8 px gap, `.row` a wrapping row with an 8 px gap. `.nowrap` keeps a figure on one line; `.scroll-box` caps a list at about five table rows and scrolls the rest.

## Component styles

All interactive components: `--font-ui` 16 px, height 40 px, focus ring 2 px `--color-accent` with 2 px offset, visible on keyboard focus only. Transitions 120 ms on background and border colour, nothing else animates except the loading indicator.

| Component | Size | Fill | Text | Border | Radius | Hover | Active / selected |
|---|---|---|---|---|---|---|---|
| Button primary | 40 px, padding 0 16 px | `--color-accent` | `--color-on-accent` | none | 8 px | fill `--color-accent-2` | fill darkens 8% |
| Button secondary | 40 px, padding 0 16 px | transparent | `--color-text` | `--color-border` | 8 px | fill `--color-surface` | fill `--color-surface-hover` |
| Button disabled | as above | `--color-surface` | `--color-text-muted` | `--color-border` | 8 px | none | none, cursor not-allowed |
| Text input | 40 px, padding 8 12 px | `--color-surface` | `--color-text`, placeholder muted | `--color-border` | 8 px | border `--color-text-muted` | focus ring, border `--color-accent` |
| Dropdown | as text input, chevron right, 16 px, `--color-text` | `--color-surface` | `--color-text` | `--color-border` | 8 px | as text input | open: border `--color-accent`, list is a card with menu items |
| Card | padding 16 px | `--color-surface` | `--color-text` | `--color-border` | 12 px | none | none |
| Table | cell padding 12 16 px | header `--color-surface`, rows `--color-bg` | header label, cells body | row divider `--color-border` bottom only | 12 px on the outer card | row `--color-surface-hover` | row gets 2 px left border `--color-accent` |
| Menu item | 40 px, padding 0 12 px | transparent | `--color-text` | none | 8 px | `--color-surface-hover` | `--color-surface-hover` plus 2 px left border `--color-accent` |
| Badge | 20 px, padding 0 8 px | state `-bg` token, or `--color-accent-3` for a count | small, state token, or `--color-on-accent` on the count badge | none | 999 px | none | none |
| Chip | secondary button | transparent | body | `--color-border` | 8 px | as secondary button | as secondary button; fills the input and submits |
| Switch | 40 by 24 px pill | `--color-surface`, `--color-accent` when on | none | `--color-border` | 999 px | none | knob moves right, `--color-on-accent` |
| Health dot | 40 px button holding a 10 px circle | circle: `--color-border` until checked, then success, warning or error | none | none | round | fill `--color-surface` | click opens a card with one row per check |
| Loading indicator | 16 px circle | 2 px ring, `--color-border` with a `--color-accent-2` arc | none | none | round | none | spins 800 ms linear |
| Error message | padding 12 16 px | `--color-error-bg` | `--color-text`, icon `--color-error` | 2 px left `--color-error` | 8 px | none | none |
| Empty state | card, padding 48 px, centred | `--color-surface` | heading 24 px, one body line muted, secondary buttons | `--color-border` | 12 px | none | none |
| Modal | 960 px, 80 vh | `--color-bg` | body | `--color-border` | 12 px | none | backdrop `rgba(0, 0, 0, 0.6)` |

Error messages say what failed and what the user can do, in one sentence each. The loading indicator sits where the result will appear, never in the button.

## Logo, favicon

For each tool, create your own logo with a matching favicon. Spend some time on it, make it unique.

Weather Agent: a pixel mark, in the stepped-block manner of mistral.ai's own brand but with a different shape. A speech bubble of 4 px squares, six squares wide, in four warm rows top to bottom: `#fec63a`, `#ffaf01`, `#fa500f`, then a two-square tail to the bottom left in `#e51300`. Three dark squares in the second row read as the dots of someone typing: weather you can talk to. `static/logo.svg` at 32 px, `static/favicon.svg` cropped to the mark. Discrete rows, no gradient.

The settings icon is drawn in the same style: a pixel sun that is also a gear, a ring of eight squares with eight teeth, in the text colour because it is a control and not a brand mark.

## Fonts

Self-hosted in `static/fonts` as latin woff2 subsets, weight 400, so the page renders the same without network. mistral.ai loads ALT Mistral for headings, which is commercial, Inter for text and Space Mono for code. Space Grotesk is the free stand-in for ALT Mistral: a grotesque with the same technical feel, from the same designer as Space Mono. Inter and Space Mono are used as they are on mistral.ai.

## Responsive behaviour

Primary target is a 1280 px screen share. Nothing below 768 px matters.

| Width | Content column | Settings window | Tables | Cards in a row |
|---|---|---|---|---|
| 1280 | 960 px centred, 32 px page padding | Centred modal, 960 px wide, 80 vh tall, page dimmed behind | Full | Up to 3 |
| 1024 | Full width minus 24 px padding | Centred modal, full width minus 48 px | Full, small text in secondary columns | Up to 2 |
| 768 | Full width minus 16 px padding | Modal fills the width, menu becomes a row above the page | Secondary columns hidden, rows stack label over value | 1 |

The settings window has a header row with the title and the close button, a 200 px menu column and a scrolling page column. Its height is fixed at 80 vh so a page that is still loading does not change the size of the dialog. It closes on the button, Escape, or a click on the dimmed page.

Type scale, spacing and component sizes do not change with width. Only columns, panels and padding do.

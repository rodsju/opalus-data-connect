# Opalus Design System

Design system for **Grupo Opalus** — web (institutional site and internal system) and slide presentations.

## Company context

Grupo Opalus is a Brazilian long-term-care and senior-health group. Its brand values, stated on page 3 of the manual, are **Excelência · Humanização · Ética · Técnica Profissional · Apoio · Eficiência**.

The group is a holding with three controlled brands — **Opalus Geriatrics**, **Opalus Premier** and **Opalus Pleno** — which share the parent's mark structure but carry their own institutional colour pair.

**Surfaces this system covers**
1. **Site institucional** — public marketing/portal site (`ui_kits/site/`)
2. **Sistema Opalus** — internal assistential system, dashboard-and-records shaped (`ui_kits/sistema/`)
3. **Apresentações** — 16:9 slide templates (`slides/`)

### Sources given
- `uploads/Manual-da-Marca-Opalus.pdf` — *Manual de Uso da Marcas*, September 2024, 18 pages, Adobe InDesign 19.5. The only normative source: brand concept, lockups, proportions, clear space, institutional and complementary colours, monochrome version, backgrounds, and misuse rules.
- `uploads/opalus-logo-h-cor-rgb-1080px-w-72ppi.png` — the horizontal colour lockup, 1080×270, transparent. **The only raster asset supplied.**

### What was NOT provided (and therefore not recreated)
- No website, app, or system screens, no Figma file, no codebase, no live URL. The two UI kits are **brand-faithful compositions from the manual and the tokens in this repo — not recreations of an existing product.** Anywhere a design decision had no basis in the manual it is documented as such.
- No photography. Where imagery belongs, the abstract illustrations in `assets/illustrations/` stand in.
- No icon library. See ICONOGRAPHY.
- No font binaries. See VISUAL FOUNDATIONS → Type.
- No existing deck. The slide layouts are new, built from the manual's system.
- No sub-brand lockups (Geriatrics / Premier / Pleno). Page 8 of the manual shows them but supplies no files. **Do not reconstruct them** — request the files from the design team.

---

## CONTENT FUNDAMENTALS

**Language.** Brazilian Portuguese, always. The manual is written in pt-BR and the audience is Brazilian families, staff and regulators. English appears only in code identifiers.

**Register.** Institutional, plain, and calm — the tone of a hospital's clinical governance document, not of a consumer brand. The manual's own voice sets the standard: it explains *why* a rule exists before stating it, and closes uncertainty with a referral ("Em caso de dúvidas consulte a equipe de design ou a equipe de marketing"). Copy in this system does the same: it states the fact, gives the basis, and names who to ask.

**Person.** Prefer the impersonal and the first-person plural. "Deve-se utilizar a versão monocromática" (manual). "O que medimos, publicamos." Address the reader as **você** in forms and transactional UI ("Como podemos chamar você?"); never *tu*, never the formal *V.Sa.*

**Casing.** Sentence case for headlines, buttons, labels and menu items — "Nova admissão", not "Nova Admissão". Title Case only in proper names ("Opalus Premier", "Ala Norte"). ALL CAPS **only** in eyebrows, table headers and field labels, always in Barlow at 12px/0.14em tracking — never in a headline, never in a button.

**Numbers.** Brazilian conventions throughout: decimal comma, thousands point, percent with a space omitted (`92,4%`), percentage-point deltas as `p.p.`, dates as `25/08/2026`, 24-hour time (`14:32`). Metrics are set in Barlow with tabular figures so columns align.

**Length.** Headlines under nine words. Body paragraphs two to three sentences. Badges one or two words. Tooltips a few words, no final period. Alert titles are a statement of fact ("3 prescrições vencem hoje"), and the body is the instruction ("Revise antes das 18h.").

**Terminology.** *Residente* (not "paciente") in residential contexts; *paciente* in clinical/ambulatory ones. *Unidade* for a physical address; *controlada* for a sub-brand. *Colaborador* for staff. *Família* — the family is a first-class stakeholder and is named explicitly in copy.

**Emoji: never.** Not in UI, not in slides, not in marketing. The brand is clinical and the manual admits no decorative element beyond the mark. Unicode symbols are limited to the em-dash (—) as a list marker and the triangle deltas (▲ ▼) beside metrics.

**Voice examples**
- Hero: "Cuidado de longa permanência com técnica e humanidade."
- Value proof: "O que medimos, publicamos."
- CTA: "Falar com a equipe" — never "Clique aqui", never "Saiba mais".
- Empty state: "Nenhum layout de Indicadores foi fornecido no material de origem."
- Destructive confirm: "Confirmar alta? Esta ação libera o leito N-104."
- Never: "Bem-vindo à nossa família!", "Cuidando de quem você ama ❤", "Transformando o cuidado".

---

## VISUAL FOUNDATIONS

### Brand concept
The symbol composes three readings, stated on page 5 of the manual: a **cross** (nursing), a **star** (hope, energy) and a **happy, healthy individual** — the sphere reading as a head above the cross's body. Every derived graphic in this system is built from those two primitives: the rounded cross and the sphere. Nothing else is invented.

### Colour
Two institutional pairs, four complementary tones, one neutral ramp. All hex values are literal from pages 12–13.

| Role | Principal | Secundária |
|---|---|---|
| Opalus (holding) | `#233751` | `#96b4d6` |
| Controladas (Geriatrics / Premier / Pleno) | `#004e84` | `#66a5cf` |

Complementary: teal `#009597` / `#00afb9` (saúde, renovação) and purple `#663171` / `#9d7aae` (sofisticação, acolhimento). The manual is explicit that complementary colours exist for *contrast and hierarchy* — they never lead a layout. In practice: navy is the brand voice, controladas blue is the interactive/accent voice, teal is the only "live/positive" colour, purple is reserved for editorial accents and the third controlada.

Neutrals are **cool-cast**, tuned to the navy — `#141920` is the darkest ink, never `#000`. Backgrounds are white or `--navy-50`; the page tint `--grey-25` is used only in the system shell.

Max **two** background colours per deck or page: white/tint plus one navy or blue field.

### Gradients
The symbol carries a light-to-dark navy degradê (135°). The manual forbids altering it. Four derived surface gradients are tokenised (`--gradient-navy`, `--gradient-blue`, `--gradient-teal`, `--gradient-mist`) and are always **low-contrast and single-hue** — a navy that gets darker, a teal that gets deeper. There are no multi-hue gradients in this brand and specifically **no blue-to-purple gradient**, despite both colours existing in the palette.

### Type
**Onest** is the brand typeface (Light 300, Regular 400, Bold 700, Black 900 — extracted from the manual's embedded fonts). **Barlow** is the secondary face, used for UI labels, table headers and all figures because of its tabular numerals. **Minion Pro** appears once in the source PDF as an incidental InDesign default and is *not* part of the system.

⚠️ **Font substitution flagged:** no licensed binaries were supplied. Both families are loaded from Google Fonts in `tokens/fonts.css`, which is a faithful match (Onest and Barlow are both Google-hosted open-source families, so this is a like-for-like load rather than a lookalike substitution). **Ask the brand team for the licensed webfont files** if self-hosting is required; drop them in `assets/fonts/` and replace the `@import` with `@font-face` rules.

Display type is Bold/Black with tight tracking (−0.03em at 60px+). Lead paragraphs are Onest **Light 300** at 20–26px — the Light weight is the brand's signature editorial move. Body is Regular 400 at 16/1.45. No mono face is defined by the brand; `--font-mono` falls back to the system stack and is used only for token names in documentation.

### Spacing & layout
4-based scale from 2px to 128px. Content is capped at 1200px (`--container-max`) with 32px gutters. Marketing sections are 96px vertical; the system shell uses 28px page padding and 16–20px grid gaps. Fixed elements: the site header is sticky and translucent; the system sidebar (248px) and header are fixed, and only the content column scrolls.

**Área de proteção:** clear space equal to one cross-arm width (`h`) on all four sides of the mark, scaling with the mark and never with the layout.

### Backgrounds & texture
No photography was supplied. Backgrounds are, in order of preference: flat white, flat `--navy-50`, a single-hue navy/blue field, and — for hero and closing moments — a navy field carrying **one** abstract illustration at 20–28% opacity, or the symbol as a watermark at **6–9%**. A 14px radial dot grid in `--navy-300` is available for sunken panels. No noise, no grain, no photographic texture, no repeating pattern louder than the dot grid.

### Illustration
Eight near-abstract SVGs in `assets/illustrations/`, all built from the cross and sphere primitives and the palette: `data-constellation`, `signal-bars`, `pulse-trace`, `scatter-field` (data), `node-mesh`, `orbit-core`, `flow-streams`, `cross-lattice` (systems/technology). Rules: one illustration per view; never at full opacity over text; never mixed two-to-a-frame; never given a drop shadow. They stand in for photography and must be replaced by real imagery when it exists.

### Corner radii
Derived from the symbol, whose cross arms round at roughly 0.22 of the arm width — so the brand reads **soft but never pill-shaped**. 4px (checkboxes), 6px (nested chips), 10px (buttons, inputs, small cards), 14px (cards, tables), 20px (dialogs), 28px (large feature panels), `999px` for badges, tags, avatars and progress tracks only.

### Cards
White, 1px `--border-default` hairline, `--radius-lg` (14px), `--shadow-sm`. **No coloured left border, ever.** Variants: `sunken` (grey-50 fill), `accent` (navy-50 fill, navy-200 border), `brand` (navy gradient, inverse text). Interactive cards lift 2px and go to `--shadow-lg` on hover.

### Shadows
Navy-tinted, never neutral black — `rgba(35,55,81,α)`. Five steps xs→xl. Cards live at `sm`, hover at `lg`, dialogs and toasts at `xl`. One inner shadow token (`--shadow-inset`, a 1px white top highlight) for pressed surfaces. Focus is a 3px `rgba(102,165,207,.42)` ring, never a hard outline.

### Protection gradients vs capsules
Over imagery the brand uses a **protection gradient**, not a capsule: `--scrim-bottom` (navy-900 at 82% → transparent) under text, and the **white monochrome lockup** on top — the manual mandates the white version over flat fills and photography. Capsules (solid rounded plates behind a mark) are not used.

### Transparency & blur
Used sparingly, in three places only: the sticky site header (`--glass` white at 72% + 14px blur), the dialog scrim (navy at 55% + 3px blur), and sidebar nav states (white at 8/12%). Nothing else is translucent — content surfaces are always opaque.

### Motion
Calm and clinical. 140ms for colour and hover, 220ms for transforms and toggles, 340ms for bars and charts filling. Standard easing is `cubic-bezier(.2,.6,.2,1)`. **No bounce, no overshoot, no spring, no attention-seeking loops.** Entrances are a fade plus at most a 4px rise; exits are a plain fade. Charts animate height only, once, on mount.

### Hover, press, focus, disabled
- **Hover, filled:** one step darker (`navy-700 → navy-800`). **Hover, outlined/ghost:** a tint fill appears (`grey-50` or `navy-50`), border unchanged. **Hover, card:** 2px lift + deeper shadow. Never a scale-up, never an opacity fade.
- **Press:** two steps darker (`navy-900`). No shrink transform — the brand doesn't squash.
- **Focus:** 3px blue ring (`--shadow-focus`); danger controls get the red ring.
- **Disabled:** 45% opacity, no colour change, `not-allowed` cursor.
- **Selected:** filled navy for tags and pill tabs; a 2px navy inset underline for underline tabs; `--surface-selected` for rows.

### Borders
1px hairlines almost everywhere (`--grey-200`). 2px only as a selection indicator or a chart baseline. Table rows are separated by `--grey-100`, one step lighter than container borders, so the grid recedes. On navy, borders are `rgba(255,255,255,.16)`.

### Data visualisation
Baseline rule only — no gridlines, no plot border, no boxed legend; legends are inline dot-and-label rows. The categorical sequence `--chart-1…8` runs institutional-first (navy → blue → light blue → teal → purple). Single-series charts use one colour (navy) with at most one bar promoted to teal to mark the point being made.

**Vivid (relatórios).** Para as telas de `/reports` existe uma segunda família, `--vivid-*` (blue, cyan, teal, violet, magenta, coral, amber, green, cada uma com `-soft`), e a sequência `--chart-vivid-1…8`. É mais saturada de propósito: separa séries empilhadas e dá peso aos KPIs. Uso restrito a dados — gráficos, chips de KPI (`--gradient-kpi-*`), barras de participação e o hero de relatório (`--gradient-report`). Botões, menu, links e texto continuam na paleta institucional. Semântica em relatório: `--report-positive` (teal) para bom/recuperado, `--report-negative` (coral) para glosa/perda, `--report-attention` (amber) para pendente.

---

## ICONOGRAPHY

**No icon set was supplied with the brand** — the manual contains only the mark, and the single PNG has no glyph set. Substitution flagged:

⚠️ **Icons are [Lucide](https://lucide.dev) 0.544.0, loaded from CDN** (`https://unpkg.com/lucide@0.544.0/dist/umd/lucide.js`), rendered through the `Icon` component at **1.75px stroke** with rounded caps — the closest match to the symbol's soft, even-weight, geometric construction. This is a substitution, not a brand asset. **If Opalus has an internal icon library, send it and this will be swapped.**

- **Style:** outline only, uniform stroke, no filled glyphs, no duotone, no coloured icons except a semantic status colour.
- **Sizes:** 16px in dense tables and small badges, 18–20px in buttons and nav, 22–24px in section headers and feature tiles.
- **Colour:** inherits `currentColor`. Standalone feature icons sit on a 44px `--navy-50` rounded tile in `--navy-700`.
- **Emoji: never used.** **Unicode as icons:** only the em-dash list marker and ▲/▼ metric deltas.
- **The mark is not an icon.** `assets/symbol.png` is used as an app icon, favicon and watermark — never inline in a text run, never as a bullet.

---

## Index

**Root**
- `styles.css` — the single entry point consumers link. `@import` lines only.
- `thumbnail.html` — homepage tile.
- `SKILL.md` — Agent Skills wrapper.
- `readme.md` — this file.

**`tokens/`** — `fonts.css` · `colors.css` · `typography.css` · `spacing.css` · `radii.css` · `elevation.css` · `motion.css` · `semantic.css` · `base.css`

**`assets/`** — `logo-horizontal{,-white,-mono}.png` · `logo-vertical{,-white,-mono}.png` · `symbol{,-white,-mono}.png` · `illustrations/` (8 SVGs)

**`guidelines/`** — 25 specimen cards feeding the Design System tab: Brand (8), Colors (7), Type (5), Spacing (5).

**`components/`** — 26 components in five groups.

- **core/** — `Button`, `IconButton`, `Icon`, `Badge`, `Tag`, `Card`, `Logo`
- **forms/** — `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `Radio`, `Switch`
- **navigation/** — `TopBar`, `SideNav`, `Tabs`, `Breadcrumbs`
- **feedback/** — `Alert`, `Toast`, `Tooltip`, `Dialog`
- **data/** — `StatCard`, `DataTable`, `ProgressBar`, `BarChart`

Each has a sibling `.d.ts` (props contract) and `.prompt.md` (what & when + usage).

**Intentional additions.** The brand supplied no component inventory, so the standard primitive set was authored. Beyond it, four additions, each with a reason: **`Logo`** — so the supplied lockup files are always used instead of retypeset; **`Icon`** — a wrapper so the Lucide substitution lives in one file and can be swapped wholesale; **`StatCard` / `BarChart` / `DataTable` / `ProgressBar`** — the brief is explicitly a data-and-technology system and both target surfaces are metric-led; **`Field`** — label/hint/error is repeated across every form control.

**`ui_kits/`**
- `site/` — institutional website: `HomePage`, `UnitsPage`, `ContactPage`, `Shared`, `index.html`
- `sistema/` — internal system: `AppShell`, `Dashboard`, `PatientList`, `PatientDetail`, `index.html`

**`slides/`** — nine 16:9 layouts: `title`, `section`, `agenda`, `metrics`, `chart`, `comparison`, `quote`, `units`, `closing`.

**`templates/deck/`** — a copyable starting deck for consuming projects.

---
name: Obsidian Capital
colors:
  surface: '#10131a'
  surface-dim: '#10131a'
  surface-bright: '#363940'
  surface-container-lowest: '#0b0e14'
  surface-container-low: '#191c22'
  surface-container: '#1d2026'
  surface-container-high: '#272a31'
  surface-container-highest: '#32353c'
  on-surface: '#e0e2eb'
  on-surface-variant: '#bacac1'
  inverse-surface: '#e0e2eb'
  inverse-on-surface: '#2d3037'
  outline: '#85948c'
  outline-variant: '#3c4a43'
  surface-tint: '#2fe0aa'
  primary: '#44edb7'
  on-primary: '#003828'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#006c4f'
  secondary: '#adc6ff'
  on-secondary: '#002e6a'
  secondary-container: '#0566d9'
  on-secondary-container: '#e6ecff'
  tertiary: '#cad2f1'
  on-tertiary: '#273047'
  tertiary-container: '#aeb7d5'
  on-tertiary-container: '#3f4861'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#dae2ff'
  tertiary-fixed-dim: '#bdc6e4'
  on-tertiary-fixed: '#121b31'
  on-tertiary-fixed-variant: '#3d465f'
  background: '#10131a'
  on-background: '#e0e2eb'
  surface-variant: '#32353c'
  emerald-hover: '#00B386'
  surface-deep: '#080B11'
  surface-canvas: '#0E131F'
  surface-card: '#141B2D'
  surface-card-elevated: '#1A233A'
  border-subtle: rgba(255, 255, 255, 0.08)
  border-structural: '#25324E'
  warning-amber: '#F59E0B'
  refusal-crimson: '#EF4444'
typography:
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 44px
    fontWeight: '700'
    lineHeight: 52px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  metric-display:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system embodies high-frequency precision, institutional poise, and modern retail execution. It sits directly at the intersection of developer-first tooling (Linear), infrastructure-grade reliability (Stripe), and hyper-accessible investment platforms (Groww).

The visual language is characterized by an ultra-sleek, deep-slate dark mode constructed from stacked optical surfaces, precise 1px architectural borders, and energetic electric-mint interactions. It avoids loud decorative noise in favor of data density, crisp glassmorphic layering, and strict geometric clarity.

Targeting retail investors, institutional traders, and fintech builders, the UI evokes supreme calm, speed, and analytical confidence. Financial feedback is instant, unambiguous, and mathematically balanced.

## Colors

The foundation is built upon deep obsidian tones (`#080B11` and `#0E131F`) calibrated to reduce glare during prolonged market sessions while giving financial data maximum luminous clarity.

- **Primary (`#00D09C`)**: The emerald growth signature. Reserved for positive market movements, portfolio gains, high-intent call-to-actions, and primary confirmations. Hover states compress slightly to `#00B386`.
- **Secondary (`#3B82F6`)**: Royal Indigo. Emphasizes informational infrastructure, active navigational states, multi-asset diversification indicators, and deep-link interactive anchors.
- **Tertiary (`#1A233A`)**: Deep structural slate utilized for interactive fills, segmented control backs, and raised card headers.
- **Neutral (`#080B11`)**: The baseline canvas depth against which all cards and modal sheets layer.
- **System Diagnostics**: Warning Amber (`#F59E0B`) highlights risk advisories, margin calls, and volatility warnings. Refusal Crimson (`#EF4444`) signals negative delta, order cancellations, and security alerts.

## Typography

Typography balances geometric authority with utility. Plus Jakarta Sans handles high-level titles and module anchors, imparting a refined technological stance. Inter governs body copy, transactional flows, labels, and all data metrics.

All numerical figures, currency displays, percentage deltas, and book quantities must enforce `font-feature-settings: "tnum" 1, "cv05" 1` (tabular figures and crisp zero slash) to prevent jumping or visual stutter during active tick updates. Line heights are intentionally tight to maintain analytical density.

## Layout & Spacing

The layout is built on a responsive 12-column grid system paired with strict 4px/8px incremental rhythm units:

- **Desktop (>= 1200px)**: 12-column layout with 24px gutters (`gutter-desktop`) and 40px outer margins (`margin-desktop`). Maximum content bounding box is 1440px centered.
- **Tablet (768px - 1199px)**: 8-column layout with 16px gutters and 24px margins (`margin-tablet`).
- **Mobile (< 768px)**: 4-column layout with 16px gutters and 16px outer edge margins (`margin`).

Data dense components (order books, execution logs, ticker strips) leverage compact padding (`space-xs` and `space-sm`), whereas high-level portfolio cards, deposit sheets, and onboarding flows use expansive containment (`space-lg` to `space-xl`).

## Elevation & Depth

Visual depth avoids heavy, muddy drop-shadows, relying instead on structural luminance staging, translucent dark glass, and fine hairline borders.

- **Level 0 (Canvas Base)**: `#080B11` solid. Recessed backdrop for market grids and workspace scaffolds.
- **Level 1 (Sub-canvas / Panels)**: `#0E131F` with a 1px border of `#25324E`. Used for static sidebars, auxiliary tool trays, and navigation docks.
- **Level 2 (Translucent Cards)**: Backed by `rgba(20, 27, 45, 0.75)` with a backdrop blur filter of `16px` to `24px` and a fine rim border of `rgba(255, 255, 255, 0.08)`. Subtle ambient shadow: `0 8px 32px -4px rgba(0, 0, 0, 0.5)`.
- **Level 3 (Interactive Overlays & Modals)**: `#1A233A` with `rgba(255, 255, 255, 0.12)` rim highlighting and an ambient shadow of `0 20px 48px -8px rgba(0, 0, 0, 0.8)`.
- **Glow Accents**: Primary action buttons and positive tick updates project a directional volumetric aura via `box-shadow: 0 0 24px rgba(0, 208, 156, 0.22)`.

## Shapes

The design uses a balanced roundedness (Level 2). This delivers modern software approachability without softening into casual or child-like geometries:

- Standard cards, panels, and modals use `rounded-lg` (1rem / 16px).
- Action buttons, form fields, and dropdown containers use standard radius (0.5rem / 8px).
- Metric chips, ticker pills, and dynamic status tags take `rounded-xl` (1.5rem / 24px) or full circular caps to preserve distinct element grouping.

## Components

### Buttons
- **Primary**: Solid emerald `#00D09C` background with bold deep obsidian text (`#080B11`). Micro-glow on hover, background transitions to `#00B386`. Height: 40px (regular), 32px (compact). Padding: `space-sm` `space-md`. Border radius: 8px.
- **Secondary**: Elevated slate surface (`#1A233A`) with subtle border (`rgba(255, 255, 255, 0.08)`), white text (`#FFFFFF`), and blue highlight on hover (`border-color: #3B82F6`).
- **Tertiary / Ghost**: Transparent fill, muted text (`#8E9BAE`), transitioning to `rgba(255, 255, 255, 0.05)` fill on hover.

### Inputs & Form Elements
- **Input Fields**: Elevated background `#0E131F`, 1px border of `#25324E`. Padding `space-sm` `space-md`. Typography uses `body-md` in pure white with placeholder in `#5A677F`. On focus: 1px outline in `#3B82F6` and subtle glow `0 0 0 3px rgba(59, 130, 246, 0.15)`.
- **Checkboxes & Radios**: 16px square/circle with `#141B2D` background and `#25324E` border. Selected state fills with `#00D09C` featuring a sharp white checkmark or center pip.

### Cards & Analytical Panels
- Glassmorphic translucent slate cards (`#141B2D` at 75-80% opacity) overlaid on `#080B11` canvas with `backdrop-filter: blur(16px)`. Border is strictly 1px `rgba(255, 255, 255, 0.08)`. Internal padding defaults to `space-lg`.

### Chips & Badges
- **Gain Delta**: Fill `rgba(0, 208, 156, 0.12)`, text `#00D09C`, border `1px solid rgba(0, 208, 156, 0.25)`. Tabular figures only.
- **Loss Delta**: Fill `rgba(239, 68, 68, 0.12)`, text `#EF4444`, border `1px solid rgba(239, 68, 68, 0.25)`.
- **Status / Advisory**: Warning Amber (`rgba(245, 158, 11, 0.12)` fill, `#F59E0B` text).

### Lists & Tables
- Border-separated item rows using `rgba(255, 255, 255, 0.05)`. Alternating row highlights avoided; instead, use interactive hover highlight `rgba(255, 255, 255, 0.03)` with `transition: background 150ms ease`. All cell metrics align right with tabular numerical alignment.
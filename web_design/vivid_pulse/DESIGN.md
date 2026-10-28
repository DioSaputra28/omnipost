---
name: Vivid Pulse
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#d0bcff'
  on-secondary: '#3c0091'
  secondary-container: '#571bc1'
  on-secondary-container: '#c4abff'
  tertiary: '#4cd7f6'
  on-tertiary: '#003640'
  tertiary-container: '#009eb9'
  on-tertiary-container: '#002f38'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#e9ddff'
  secondary-fixed-dim: '#d0bcff'
  on-secondary-fixed: '#23005c'
  on-secondary-fixed-variant: '#5516be'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-hero:
    fontFamily: Josefin Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-hero-mobile:
    fontFamily: Josefin Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Josefin Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Josefin Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: 0em
  headline-md:
    fontFamily: Josefin Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: 0em
  headline-sm:
    fontFamily: Josefin Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: 0.01em
  title-md:
    fontFamily: Josefin Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0.02em
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-sm: 1rem
  gutter-lg: 2rem
  margin: 2rem
  margin-mobile: 1rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style
The design system establishes a focused, high-precision control center tailored for digital strategists, creators, and enterprise social media operations. Balancing analytical capability with creative velocity, the interface projects calm mastery through deliberate negative space, restrained structural lines, and focused chromatic impact.

### Visual Style Direction
The aesthetic merges Modern Corporate structure with selective Glassmorphism and ambient layered surfaces. High-density data workspaces (post schedulers, multi-account streams, campaign analytics) avoid visual fatigue by utilizing neutral slate foundations. Vibrant deep indigo and electric violet tokens remain reserved for primary drivers, focal metrics, and conversion paths. Translucent frosted sheets, crisp sub-pixel boundaries, and rounded contours build a polished, fluid, and professional workspace.

## Colors
The color architecture relies on a dark-first foundation designed to minimize eye strain during extensive scheduling and monitoring sessions, while ensuring prominent readability for dense content grids.

### Palette Hierarchy & Intent
- **Primary (`#6366F1` - Electric Indigo):** Primary calls-to-action, active workspace states, key timeline trackers, and highlighted operational states.
- **Secondary (`#8B5CF6` - Vivid Violet):** Secondary engagement metrics, multi-channel campaign differentiators, and dynamic gradient accents paired with the primary token.
- **Tertiary (`#06B6D4` - Digital Cyan):** Real-time analytics pings, live status badges, positive delta metrics, and cross-channel sync indicators.
- **Neutral (`#0F172A` - Deep Slate):** Anchors the tonal canvas across varying surface values (`#090D16` root canvas, `#0F172A` structural backdrop, `#1E293B` panel containers, and `#334155` border delimiters).

### Surface Layers & Contrast
- **Canvas Base:** `#090D16` provides the deep non-distracting canvas.
- **Panel Containers:** `#0F172A` with selective `rgba(30, 41, 59, 0.7)` translucency.
- **High-Contrast Text:** `#F8FAFC` for headline headers and key numbers, `#94A3B8` for secondary labels, metadata, and structural microcopy.
- **Functional States:** Success (`#10B981`), Warning (`#F59E0B`), and Critical Error (`#EF4444`) maintain optical balance against dark slate grounds.

## Typography
Typography creates a strong architectural contrast between stylistic brand identity and functional UI clarity.

### Family Pairing
- **Headings & Metric Displays (`Josefin Sans`):** Provides sharp, elegant geometric character. Used for dashboard widget titles, metric aggregates, navigation category headings, and high-impact hero statements.
- **Interface & Content (`Plus Jakarta Sans`):** Delivers clean readability for body copy, social feed text streams, data charts, and control interfaces.

### Application Rules
- Maintain tracking discipline: `Josefin Sans` requires tight letter spacing in large formats (`-0.02em`) and slight expansion in section labels (`0.02em`) to maintain geometric clarity.
- Avoid all-caps formatting for `Josefin Sans` outside of small eyebrow tags and metadata markers (`label-sm`).
- Social media body previews inherit the system body specifications (`body-md`) with neutral-light coloration (`#E2E8F0`) to mirror native platform readability.

## Layout & Spacing
The layout follows a responsive 12-column fluid grid tailored to complex multi-panel dashboard views and schedule timelines.

### Breakpoint Structure & Reflow
- **Desktop (1280px+):** 12-column fluid layout with a fixed or collapsible 260px navigation sidebar, `2.5rem` outer canvas margins, and `1.5rem` internal gutters. Complex analytics widgets span 3, 4, 6, or 12 columns.
- **Tablet (768px - 1279px):** 8-column layout. The primary navigation converts to an icon rail or collapsible drawer. Margins reduce to `1.5rem` with `1rem` gutters. Multi-stream columns switch to a tabbed view or horizontal scroll snap.
- **Mobile (Below 768px):** 4-column single-column flow with `1rem` outer screen padding. Interactive calendars convert to single-day stacked cards; high-density analytical charts offer targeted horizontal swipe-views.

### Spacing Principles
All layout values adhere strictly to an 8pt base grid system (augmented with a 4pt sub-token via `space-xs`). Use `space-sm` (8px) for tightly coupled items such as label-to-input gaps, and `space-md` (16px) for intra-card padding and feed component elements.

## Elevation & Depth
Depth is established through layered translucent materials, subtle boundary borders, and soft colored shadows rather than heavy drop shadows.

### Surface Elevation Tiers
- **Tier 0 (Root Canvas):** `#090D16` base layer. Deep and non-reflective.
- **Tier 1 (Base Cards & Feed Streams):** Solid `#0F172A` or semi-transparent `rgba(15, 23, 42, 0.75)` with `backdrop-filter: blur(16px)`. Enclosed with a `1px` subtle outline of `rgba(255, 255, 255, 0.07)`.
- **Tier 2 (Floating Cards & Hover States):** `rgba(30, 41, 59, 0.7)` with `backdrop-filter: blur(20px)`, a `1px` outline of `rgba(255, 255, 255, 0.12)`, and an ambient tinted shadow: `0 12px 32px -4px rgba(0, 0, 0, 0.4), 0 4px 16px -2px rgba(99, 102, 241, 0.08)`.
- **Tier 3 (Dropdowns, Overlays & Modals):** `rgba(15, 23, 42, 0.9)` with `backdrop-filter: blur(28px)`, structural border of `rgba(99, 102, 241, 0.25)`, and a deep protective shadow: `0 24px 48px -8px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08)`.

### Border Integrity
Avoid high-contrast separation lines. All visual division between panels, table rows, and card bodies uses subtle sub-pixel strokes (`rgba(255, 255, 255, 0.06)` or `rgba(148, 163, 184, 0.1)`).

## Shapes
The shape system uses a balanced, contemporary rounded corner language (`roundedness: 2`) that softens the analytical layout without sacrificing layout density.

### Corner Radius Implementation
- **Small Controls (`0.5rem` / 8px):** Badges, inline tags, small icon buttons, checkbox frames, and nested input elements.
- **Standard UI Elements (`1rem` / 16px):** Content cards, post preview frames, dashboard widgets, modal views, and primary action buttons.
- **Large Containers (`1.5rem` / 24px):** Primary app navigation panels, slide-out drawer views, contextual empty states, and post composer containers.
- **Pill Exceptions (`9999px`):** Status indicators, account avatars, channel picker tags, and platform filter switches.

## Components

### Iconography
All UI icons follow a 1.5px to 2px stroke outline weight directly aligned with Heroicons Outline. Icons sit inside strict 20x20px or 24x24px viewports with optical centering. In active navigation and accent states, icons inherit the primary indigo or violet hue.

### Buttons
- **Primary:** Background tinted with an indigo-to-violet gradient (`linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)`), text `#FFFFFF`, roundedness `0.5rem`, horizontal padding `1.25rem`, vertical padding `0.625rem`. Subtle glow shadow on hover (`0 0 20px rgba(99, 102, 241, 0.35)`).
- **Secondary / Glass:** Background `rgba(255, 255, 255, 0.05)`, border `1px solid rgba(255, 255, 255, 0.12)`, text `#F8FAFC`. Background transitions to `rgba(255, 255, 255, 0.09)` on hover.
- **Ghost:** Text `#94A3B8`, background transparent. Hover transitions text to `#F8FAFC` and background to `rgba(255, 255, 255, 0.04)`.

### Input Fields & Search Bars
- Background `rgba(15, 23, 42, 0.6)`, border `1px solid rgba(255, 255, 255, 0.08)`, border radius `0.5rem`.
- Text `#F8FAFC` with placeholder `#64748B`.
- Focus state applies a border color of `#6366F1` and a soft focus ring (`0 0 0 3px rgba(99, 102, 241, 0.2)`).

### Cards & Dashboards Widgets
- Rendered with Tier 1 frosted slate surfaces.
- Widget headers display `Josefin Sans` (`title-md`) in `#F8FAFC` paired with an outline action icon (`#64748B`).
- Content body has a clean `space-md` internal offset. Border separators use `1px solid rgba(255, 255, 255, 0.06)`.

### Chips & Social Platform Badges
- Account/platform badges incorporate a pill shape with a semi-transparent base (`rgba(255, 255, 255, 0.06)`), an outline icon, and an active color indicator (e.g., cyan for active scheduled streams, emerald for published status).

### Checkboxes & Switches
- Checkboxes: 18x18px squares with `4px` corner radii, framed with `rgba(255, 255, 255, 0.2)`. Selected state fills with `#6366F1` and displays a crisp white checkmark.
- Switches: 40x22px pill frame with a 16px circular toggle thumb. Off-state `#1E293B`, on-state gradient indigo/violet.

### Post Composer & Scheduler (Domain-Specific Component)
- Multi-channel post creation workspace featuring dual-pane composition: draft editor on the left and instant mobile preview on the right.
- Timeline selector uses a glassmorphic calendar track with interactive pill markers representing scheduled post slots. Drag-and-drop actions surface a glowing violet boundary outline (`#8B5CF6`).
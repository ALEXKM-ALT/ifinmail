---
name: Institutional Precision
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002113'
  on-tertiary-container: '#009668'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
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
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  code-md:
    fontFamily: jetbrainsMono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  sidebar-width: 280px
  container-max-width: 1280px
  gutter: 24px
  margin-mobile: 16px
  stack-gap: 12px
  section-gap: 40px
---

## Brand & Style

The brand personality of the design system is anchored in **Institutional Precision**. Designed for technical administrators managing critical mail infrastructure, the UI must project an image of absolute stability, security, and functional clarity. The emotional response should be one of "calm control"—the user should feel that the system is powerful yet predictable.

The design style follows a **Modern Corporate** aesthetic with a heavy emphasis on **Minimalism**. It avoids unnecessary ornamentation in favor of high-density information layout, logical grouping, and a clear visual hierarchy. By utilizing a disciplined color palette and systematic spacing, the design system ensures that complex configuration tasks remain manageable and error-free.

## Colors

The color strategy for the design system is built on a foundation of high-contrast neutrals to differentiate administrative zones from content zones.

- **Primary (Slate Navy):** Used exclusively for the sidebar and structural navigation to provide a sense of grounded authority and depth.
- **Secondary (Action Blue):** Reserved for primary calls to action, active states, and selection indicators. This blue is vibrant enough to stand out against white backgrounds but remains professional.
- **Semantic Accents:** Success (Green), Alert (Red), and Warning (Amber) use industry-standard hues to communicate system status instantaneously.
- **Backgrounds:** The main staging area uses a crisp white background, while secondary containers use a very light slate gray to create subtle visual grouping without adding noise.

## Typography

The design system utilizes **Inter** as its primary typeface due to its exceptional legibility in technical interfaces and high-density dashboards. 

- **Headlines:** Use a tighter letter-spacing and semi-bold weights to establish a clear structural anchor for each configuration page.
- **Labels:** Use uppercase styling with increased letter-spacing for field headers and metadata titles to distinguish them from user-editable content.
- **Monospaced Data:** For IP addresses, server logs, and cryptographic keys, the system integrates **JetBrains Mono** to ensure character distinction (e.g., 0 vs O) is maintained.
- **Responsive Scaling:** Mobile views should collapse `headline-lg` to `24px` to maintain a comfortable reading width on narrow viewports.

## Layout & Spacing

The layout is structured around a **Fixed Sidebar + Fluid Content** model.

1.  **Navigation Sidebar:** A fixed 280px vertical bar on the left contains the primary application architecture. This area uses high-contrast navy backgrounds to separate "system-level" navigation from "task-level" content.
2.  **Main Content Area:** Follows a 12-column grid system. On desktop, content is capped at 1280px to prevent long-form configuration lines from becoming unreadable.
3.  **Spacing Rhythm:** The design system uses an 8px base unit. 24px gutters are standard between cards, while a tighter 12px "stack-gap" is used for elements within a group (e.g., a label and its input).
4.  **Responsive Behavior:** On tablet, the sidebar collapses into a 64px icon-only rail. On mobile, the sidebar is hidden behind a hamburger menu, and horizontal margins are reduced to 16px.

## Elevation & Depth

This design system avoids heavy shadows to maintain a clean, professional "flat-plus" appearance. Depth is communicated through:

- **Tonal Layering:** The base background is white (#FFFFFF). Cards and containers are defined by a 1px border (#E2E8F0) rather than a shadow. A secondary background tier (#F1F5F9) is used for "well" areas like code blocks or footer bars.
- **Subtle Surface Elevation:** Only active overlays (modals and dropdowns) utilize a shadow. These shadows are extra-diffused (20px-40px blur) with a low 8% opacity to feel like ambient light rather than a physical drop.
- **Interaction States:** Hover states on interactive elements should not "lift" the element, but instead change the background fill or border color to indicate focus.

## Shapes

The design system adopts a **Soft** shape language. This choice strikes a balance between the rigid "sharp" edges of legacy enterprise software and the overly "bubbly" feel of consumer apps.

- **Standard Radius (4px):** Applied to input fields, buttons, and status indicators. This small radius keeps the interface feeling "technical" and "precise."
- **Large Radius (8px):** Used for primary content cards and containers to gently soften the overall layout.
- **Full Radius (Pill):** Used only for toggle switches and status "LED" indicators to differentiate functional status from interactive buttons.

## Components

- **Cards:** White background with a 1px Slate-200 border. Headers within cards should have a subtle bottom border to separate titles from the configuration controls.
- **Input Fields:** Use a 1px Slate-300 border. On focus, the border shifts to Action Blue with a subtle 2px outer glow (ring). Labels are placed directly above the field.
- **Toggle Switches:** Small, pill-shaped components. The "Off" state is a neutral gray, while "On" uses Action Blue. No labels inside the toggle; use external text for clarity.
- **Status Indicators (LED Style):** Small 8px circles. Green (Active), Red (Stopped/Error), Gray (Inactive), and Pulsing Blue (Syncing/Processing).
- **Navigation Sidebar:** Items should use a transparent background with a 50% opacity text. Active items receive a Slate-800 background, 100% white text, and a 3px blue vertical stripe on the left edge.
- **Buttons:** Primary buttons are solid Blue-600 with white text. Secondary buttons are ghost-style with a Slate-200 border and Slate-700 text.
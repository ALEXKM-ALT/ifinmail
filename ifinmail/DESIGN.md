**ifinmail**

**Design System**

v0.0.1 · Product & Design Standard

*This document defines the visual language, component standards, interaction principles, and accessibility requirements that govern every interface in the ifinmail platform. It applies to all surfaces: web application, mobile, printed exports, and email templates.*

| Version | 1.1 — April 2026 |
| --- | --- |
| Owner | Product &amp; Design Team |
| Status | Active — Mandatory for all new work |
| Review cycle | Quarterly |
| Changes | Added dark mode tokens, browser support, i18n guidelines, component examples, performance standards, linting requirements |

# **Contents**

**1\.** Design Principles

**2\.** Brand & Identity

**3\.** Colour System

**4\.** Typography

**5\.** Spacing & Layout

**6\.** Elevation & Shadow

**7\.** Iconography

**8\.** Motion & Animation

**9\.** Components — Buttons

**10\.** Components — Form Inputs

**11\.** Components — Badges & Status

**12\.** Components — Notifications

**13\.** Components — Tables

**14\.** Components — Modals & Dialogs

**15\.** Components — Cards

**16\.** Components — Search

**17\.** Components — Tooltips

**18\.** Components — Tabs & Pills

**19\.** Components — Navigation

**20\.** Accessibility

**21\.** Do / Don't

**22\.** Governance & Change Process

**23\.** CSS Implementation Standards

**24\.** Cross-Reference Documentation

# **1\. Design Principles**

Every design decision in the ifinmail platform is evaluated against these six principles. They are ordered by priority — when principles conflict, earlier ones take precedence.

**1.1 Clarity over Cleverness**

Every screen should communicate its purpose within three seconds. Avoid clever metaphors, ambiguous iconography, and decorative UI that adds visual weight without adding meaning. If a design requires explanation, it needs to be redesigned.

**1.2 Density is Respect**

Business users manage high volumes of information. Generous padding and large cards feel friendly in consumer apps but create friction in operational tools. Default to compact layouts that show 8–12 list items per viewport. Let users see more, scroll less. The density tier framework is defined in `docs/cross-platform-typography-compactness-standard.md` §4 — Compact (default), Standard, and Comfortable tiers with per-user persistence.

**1.3 Colour Earns its Place**

Colour is the highest-attention element in any interface. Use it sparingly so it retains meaning. Blue means interactive. Red means destructive or critical. Amber means caution. Green means success. Any use of colour outside these roles must be explicitly justified.

**1.4 Ambient, Not Alarming**

Alerts, notifications, and status indicators should surface information calmly into the user's workflow, not demand attention through size, animation, or visual noise. Reserve emphatic treatments for genuinely critical states only.

**1.5 Trust the User**

Do not make every action permanently visible. Advanced actions belong in context menus, revealed on hover or via keyboard. Permanent visibility of all actions creates noise and suggests the interface does not trust the user to explore. Hide sophistication until it is needed.

**1.6 One Source of Truth**

Every UI pattern — colour, spacing, typography, component — must exist once in this system. Divergence from the system requires a formal change request. This discipline keeps the product coherent at scale across multiple teams and shipping cycles.

# **2\. Brand & Identity**

## **2.1 Wordmark**

The ifinmail wordmark uses Inter 700 in Navy (#0F2B5B). It is always set in lowercase. Minimum size is 80px width in digital, 25mm in print. Clear space on all sides equals the height of the lowercase 'i' in the mark.

*Never stretch, rotate, recolour, or apply drop shadows to the wordmark. Never place it on a background with insufficient contrast (minimum 7:1 ratio required).*

## **2.2 Logo Mark**

The 'if' icon mark is a square with 6px border radius in Blue 600. It contains the letterforms 'if' in Inter 700, white. It is used only at sizes below which the full wordmark is legible (under 24px in digital).

## **2.3 Brand Voice in UI Copy**

-   **Direct:** Use active voice. 'Save changes' not 'Changes will be saved'.
-   **Specific:** Show exact values. 'Current stock: 8 units' not 'Stock is low'.
-   **Consistent:** Use the same label for the same action everywhere. Never mix 'Delete' and 'Remove' for the same action.
-   **Calm:** Avoid exclamation marks, all-caps emphasis, and urgency language unless the situation is genuinely urgent.

# **3\. Colour System**

The ifinmail colour system uses a minimal set of purposeful tokens. Every colour has a defined role. Using a colour outside its role requires explicit sign-off from the Design lead.

| **Token / Name** | **Hex** | **Usage** |
| --- | --- | --- |
| **Blue 600 — Primary** | #1A56DB | Primary buttons, links, active states, focus rings |
| **Blue 500 — Hover** | #3B6FE8 | Button hover state, interactive element highlight |
| **Blue 100 — Tint** | #E8F0FE | Info callout backgrounds, selected row tint |
| **Blue 050 — Subtle** | #F0F4FF | Page-level hover, subtle section backgrounds |
| **Navy — Brand** | #0F2B5B | Page headers, brand marks, high-emphasis text |
| **Gray 900 — Text Primary** | #111827 | Headings, primary body text, bold labels |
| **Gray 700 — Text Secondary** | #374151 | Body copy, descriptions, secondary labels |
| **Gray 500 — Text Muted** | #6B7280 | Placeholders, timestamps, disabled labels |
| **Gray 300 — Border** | #D1D5DB | Input borders, dividers, card outlines |
| **Gray 100 — Surface 2** | #F3F4F6 | Sidebar backgrounds, zebra table rows |
| **Gray 050 — Surface 1** | #F9FAFB | Page background, subtle section fills |
| **Red 600 — Danger** | #DC2626 | Destructive actions, error states, critical alerts |
| **Red 100 — Danger Tint** | #FEE2E2 | Error message backgrounds, danger callouts |
| **Amber 600 — Warning** | #D97706 | Warning badges, caution alerts, low-stock indicator |
| **Amber 100 — Warning Tint** | #FEF3C7 | Warning message backgrounds |
| **Green 600 — Success** | #059669 | Success states, active/live badges, in-stock indicators |
| **Green 100 — Success Tint** | #D1FAE5 | Success message backgrounds |

## **3.1 Colour Usage Rules**

-   **One primary action per screen:** Only one Blue 600 primary button should be visible at a time. Multiple blue buttons dilute hierarchy.
-   **Status colours are semantic, not decorative:** Never use Red, Amber, or Green for visual decoration. Use them only for actual error, warning, and success states.
-   **Never communicate state by colour alone:** Always pair colour with a label, icon, or pattern (WCAG 1.4.1).
-   **Dark surfaces:** Use the dark mode token mappings provided below. Do not improvise dark colour values from the light palette.

## **3.2 Dark Mode Token Mappings**

The ifinmail platform supports both light and dark themes. Dark mode tokens use the same variable names with dark-specific values applied via the `@media (prefers-color-scheme: dark)` media query.

| **Token / Name** | **Light Mode** | **Dark Mode** | **Usage** |
| --- | --- | --- | --- |
| **Blue 600 — Primary** | #1A56DB | #3B82F6 | Primary buttons, links, active states |
| **Blue 500 — Hover** | #3B6FE8 | #60A5FA | Button hover state |
| **Blue 100 — Tint** | #E8F0FE | #1E3A8A | Info callout backgrounds |
| **Blue 050 — Subtle** | #F0F4FF | #172554 | Page-level hover |
| **Navy — Brand** | #0F2B5B | #1E3A8A | Page headers, brand marks |
| **Gray 900 — Text Primary** | #111827 | #F9FAFB | Headings, primary body text |
| **Gray 700 — Text Secondary** | #374151 | #D1D5DB | Body copy, descriptions |
| **Gray 500 — Text Muted** | #6B7280 | #9CA3AF | Placeholders, timestamps |
| **Gray 300 — Border** | #D1D5DB | #4B5563 | Input borders, dividers |
| **Gray 100 — Surface 2** | #F3F4F6 | #1F2937 | Sidebar backgrounds |
| **Gray 050 — Surface 1** | #F9FAFB | #111827 | Page background |
| **Red 600 — Danger** | #DC2626 | #EF4444 | Destructive actions, errors |
| **Red 100 — Danger Tint** | #FEE2E2 | #7F1D1D | Error message backgrounds |
| **Amber 600 — Warning** | #D97706 | #F59E0B | Warning badges, caution alerts |
| **Amber 100 — Warning Tint** | #FEF3C7 | #78350F | Warning message backgrounds |
| **Green 600 — Success** | #059669 | #10B981 | Success states |
| **Green 100 — Success Tint** | #D1FAE5 | #064E3B | Success message backgrounds |

### Dark Mode Implementation

```css
@media (prefers-color-scheme: dark) {
  :root {
    --ifinmail-color-text-primary: #F9FAFB;
    --ifinmail-color-text-secondary: #D1D5DB;
    --ifinmail-color-text-muted: #9CA3AF;
    --ifinmail-color-border: #4B5563;
    --ifinmail-color-surface-1: #111827;
    --ifinmail-color-surface-2: #1F2937;
    --ifinmail-color-primary: #3B82F6;
    --ifinmail-color-primary-hover: #60A5FA;
    --ifinmail-color-primary-tint: #1E3A8A;
    --ifinmail-color-danger: #EF4444;
    --ifinmail-color-warning: #F59E0B;
    --ifinmail-color-success: #10B981;
  }
}
```

**Dark Mode Rules:**
- **Always test both themes:** All components must be visually tested in both light and dark modes
- **Contrast validation:** Dark mode must maintain WCAG AA contrast ratios (minimum 4.5:1 for normal text)
- **No forced theme:** Respect user's system preference for dark/light mode
- **Manual theme toggle:** Provide user-facing theme switcher that overrides system preference when activated
- **Semantic colours unchanged:** Status colours (red/amber/green) maintain their semantic meaning, only adjust for contrast

# **4\. Typography**

ifinmail uses two typefaces: Inter for all UI text, and JetBrains Mono for numeric data, code, and value chips. Both are open-source and available via Google Fonts.

**Authoritative cross-platform standard:** The typography scale, density tiers, icon sizes, and user-customizable font offset defined in `docs/cross-platform-typography-compactness-standard.md` v0.0.1 supersede this section for all platform implementations (web, Windows, Android). The canonical scale shifts body text to 13px with a 10px hard floor and introduces three density tiers (Compact default, Standard, Comfortable) with per-user persistence.

| **Style** | **Font / Weight** | **Size** | **Line Height** | **Usage** |
| --- | --- | --- | --- | --- |
| **Display** | Inter 700 | 30px | 1.2 | Page titles, dashboard hero numbers |
| **Heading 1** | Inter 600 | 24px | 1.3 | Section titles within pages |
| **Heading 2** | Inter 600 | 20px | 1.3 | Card headers, modal titles |
| **Heading 3** | Inter 600 | 16px | 1.4 | Sub-section labels, sidebar headers |
| **Body Large** | Inter 400 | 15px | 1.6 | Primary body copy, form descriptions |
| **Body** | Inter 400 | 14px | 1.5 | Default body, table cell content |
| **Body Small** | Inter 400 | 13px | 1.5 | Secondary descriptions, helper text |
| **Label** | Inter 500 | 13px | 1.4 | Form labels, filter chips, nav items |
| **Caption** | Inter 400 | 12px | 1.4 | Timestamps, metadata, footnotes |
| **Overline** | Inter 600 | 11px | 1.4 | Section group headers (ALL-CAPS, +0.08em tracking) |
| **Code** | JetBrains Mono 400 | 13px | 1.5 | Stock values, numeric data, API keys |
| **Code Small** | JetBrains Mono 400 | 12px | 1.4 | Inline value chips (e.g. stock thresholds) |

## **4.1 Typography Rules**

-   **Never use font sizes below 12px:** Anything smaller fails WCAG contrast requirements at normal weights.
-   **Maximum two type sizes per component:** A card may have a heading (Heading 3) and body text. Adding a third size creates unnecessary complexity.
-   **Do not use font weight as the only distinguisher:** Pair weight changes with size or colour changes for clear hierarchy.
-   **Line length:** Optimal line length for body copy is 60–80 characters (approx. 480–640px at 14px). Constrain text containers to this range.
-   **Numeric data always in JetBrains Mono:** Quantities, prices, percentages, stock counts, and threshold values must always use the Code style for alignment and readability.

# **5\. Spacing & Layout**

ifinmail uses an 8px base spacing system. All spacing values are multiples of 4px (half-base). This creates natural visual rhythm and ensures components align on the underlying grid.

| **Token** | **Value** | **px** | **Usage** |
| --- | --- | --- | --- |
| **space-0.5** | 0.125rem | 2px | Icon internal padding, hairline separators |
| **space-1** | 0.25rem | 4px | Tight inline gaps (icon → label) |
| **space-2** | 0.5rem | 8px | Input internal padding (top/bottom), badge padding |
| **space-3** | 0.75rem | 12px | Input horizontal padding, compact button padding |
| **space-4** | 1rem | 16px | Standard button padding, card internal padding (sides) |
| **space-5** | 1.25rem | 20px | Card internal padding (top/bottom) |
| **space-6** | 1.5rem | 24px | Section gaps, sidebar item spacing |
| **space-8** | 2rem | 32px | Column gaps in layouts, modal padding |
| **space-10** | 2.5rem | 40px | Page section spacing |
| **space-12** | 3rem | 48px | Page top padding |
| **space-16** | 4rem | 64px | Large page section breaks |

## **5.1 Layout Grid**

| **Breakpoint** | **Min Width** | **Columns** | **Gutter** | **Margin** | **Layout** |
| --- | --- | --- | --- | --- | --- |
| **xs (mobile)** | 0px | 4 | 16px | 16px | Single column, stacked |
| **sm (tablet)** | 640px | 8 | 20px | 24px | Sidebar collapses to drawer |
| **md (laptop)** | 768px | 12 | 24px | 32px | Two-column layout active |
| **lg (desktop)** | 1024px | 12 | 28px | 40px | Standard desktop layout |
| **xl (wide)** | 1280px | 12 | 32px | 48px | Max-width 1280px, centred |
| **2xl (ultrawide)** | 1536px | 12 | 32px | auto | Layout caps at 1280px |

## **5.2 Page Layout Structure**

Every page in ifinmail follows this structural hierarchy:

-   **Top navigation bar:** 64px height. Contains logo mark, global search, user avatar, and notification bell.
-   **Left sidebar:** 240px width, collapsible to 64px (icon-only). Contains primary navigation.
-   **Content area:** Fills remaining viewport. Maximum content width 1280px, centred.
-   **Page header:** Contains page title, badge count (if applicable), and primary page actions (right-aligned).
-   **Content body:** 48px top padding, 32px bottom padding. Children use space-6 (24px) vertical gaps between sections.

*The filter sidebar pattern (used in the current Notifications page) is a legacy pattern being phased out. New pages should use horizontal chip filter bars above the content list, not vertical sidebars.*

# **6\. Elevation & Shadow**

Elevation communicates the layering hierarchy of interface elements. Use the minimum elevation level required — do not apply shadow for decoration.

| **Level** | **CSS Shadow** | **Usage** |
| --- | --- | --- |
| **0 — Flat** | none | Default page surface, list rows |
| **1 — Raised** | 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06) | Cards, sidebar panels, filter boxes |
| **2 — Floating** | 0 4px 12px rgba(0,0,0,0.10), 0 2px 4px rgba(0,0,0,0.06) | Dropdowns, popover menus, date pickers |
| **3 — Overlay** | 0 8px 24px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.08) | Modals, dialogs, command palette |
| **4 — Toast** | 0 16px 40px rgba(0,0,0,0.16), 0 6px 12px rgba(0,0,0,0.10) | Toast notifications, drag-and-drop previews |

*Never apply shadow to elements at the same elevation level as their parent. A card inside a card should not have a shadow — use a border instead.*

# **7\. Iconography**

ifinmail uses Lucide Icons v0.400+ as its icon library. Lucide provides consistent 24px grid icons at 1.5px stroke weight, which matches the visual rhythm of Inter at body text sizes.

| **Size** | **px** | **Context** |
| --- | --- | --- |
| **xs** | 14px | Inline icons inside dense table rows, badge icons |
| **sm** | 16px | Form field icons, dropdown indicators, button icons |
| **md** | 20px | Notification icons, nav item icons (default) |
| **lg** | 24px | Page action icons, empty state icons |
| **xl** | 32px | Feature illustration accents, onboarding |
| **2xl** | 48px | Empty state hero icons, error page illustrations |

## **7.1 Icon Usage Rules**

-   **Always pair with a label:** Icon-only controls require an aria-label. For non-developer contexts, always show a visible text label alongside the icon.
-   **Consistent colour:** Icons inherit their parent text colour by default. Only use coloured icons for status (e.g. a red warning icon, a green checkmark).
-   **Stroke weight is fixed:** Never apply bold or increased stroke weight to Lucide icons. For greater visual weight, increase the icon size instead.
-   **No filled variant mixing:** Do not mix outlined (stroke) and filled icon variants in the same view. The entire product uses stroke variants only.
-   **Source category colours (notification icons):** Inventory = Amber 600. System = Blue 600. Approvals = Green 600. Finance = Navy. User events = Gray 500.

# **8\. Motion & Animation**

Animation in ifinmail serves one purpose: to orient the user to changes in state. It is never decorative. All animations respect the user's prefers-reduced-motion system setting.

| **Token** | **Duration** | **Easing** | **Usage** |
| --- | --- | --- | --- |
| **instant** | 0ms | — | State changes with no perceptible delay (colour toggle) |
| **fast** | 100ms | ease-out | Hover state in/out, focus ring appearance |
| **normal** | 180ms | ease-in-out | Button press feedback, tooltip appear |
| **slow** | 280ms | cubic-bezier(.4,0,.2,1) | Panel slide, dropdown open, page transition |
| **deliberate** | 400ms | cubic-bezier(.4,0,.2,1) | Modal enter, full-page loading state |

## **8.1 Animation Rules**

-   **Enter animations:** Elements entering the screen use opacity 0 → 1 + translateY(4px) → 0 with the 'slow' token (280ms).
-   **Exit animations:** Elements leaving use opacity 1 → 0 + scale(0.98) → dismiss. Collapsing rows additionally animate max-height 0 with overflow hidden.
-   **List stagger:** When a list of items animates in, stagger each item by 40ms (max 5 items — after that, load instantly).
-   **No bounce or spring:** Elastic easing does not suit business application interfaces. Use cubic-bezier(.4,0,.2,1) (Material standard easing) for all transitions.
-   **Loading states:** Use skeleton screens (grey shimmer blocks), not spinner icons, for content loading states over 300ms.

# **9\. Components — Buttons**

| **Variant** | **Background** | **Text** | **Border** | **Usage** |
| --- | --- | --- | --- | --- |
| **Primary** | #1A56DB | White | None | Main CTA — one per screen |
| **Secondary** | White | #1A56DB | 1px #1A56DB | Secondary actions alongside primary |
| **Ghost** | White | #374151 | 1px #D1D5DB | Tertiary, header utility buttons |
| **Danger** | #DC2626 | White | None | Destructive actions only |
| **Disabled** | #F3F4F6 | #9CA3AF | 1px #E5E7EB | Any button in disabled state |

## **9.1 Button Specifications**

-   **Height:** 36px (compact), 40px (default), 48px (large / prominent CTA only).
-   **Padding:** 12px horizontal for compact, 16px for default, 20px for large.
-   **Border radius:** 8px. Consistent across all button variants.
-   **Icon buttons:** When a button contains only an icon, use a 36×36px or 40×40px square with the same border radius.
-   **Loading state:** Replace button label with a 16px spinner icon. Disable the button. Preserve the button's width to prevent layout shift.
-   **Button hierarchy:** Primary (one per screen) → Secondary (alongside primary) → Ghost (utility actions). Never show two Primary buttons in the same view.

# **10\. Components — Form Inputs**

| **State** | **Border** | **Background** | **Shadow / Ring** |
| --- | --- | --- | --- |
| **Default** | 1px #D1D5DB | #FFFFFF | None |
| **Hover** | 1px #9CA3AF | #FFFFFF | None |
| **Focus** | 1px #1A56DB | #FFFFFF | 0 0 0 3px rgba(26,86,219,0.15) |
| **Filled** | 1px #D1D5DB | #FFFFFF | None |
| **Error** | 1px #DC2626 | #FFFFFF | 0 0 0 3px rgba(220,38,38,0.12) |
| **Disabled** | 1px #E5E7EB | #F9FAFB | None |

## **10.1 Input Specifications**

-   **Height:** 40px for single-line inputs. Textarea: min-height 80px, resizable vertically.
-   **Border radius:** 8px.
-   **Label:** Always visible above the input. Never use placeholder as a label substitute. Label: 13px Inter 500, Gray 700.
-   **Helper text:** 12px Inter 400, Gray 500. Displayed below input. Replaced by error text on validation failure.
-   **Error text:** 12px Inter 400, Red 600. Always accompanies the red error border — never colour alone.
-   **Required indicator:** Red asterisk (\*) after the label text. Include '\* Required fields' caption above the form.
-   **Select / Dropdown:** Same dimensions as text input. Custom chevron icon (16px, Gray 500). Use the Ghost button style for filter dropdowns outside of forms.

# **11\. Components — Badges & Status**

| **Variant** | **Fill** | **Text Colour** | **When to use** |
| --- | --- | --- | --- |
| **Info** | #E8F0FE | #1A56DB | Neutral counts, unread indicators |
| **Success** | #D1FAE5 | #059669 | Active, fulfilled, in-stock, completed |
| **Warning** | #FEF3C7 | #D97706 | Low stock, pending, at-risk |
| **Danger** | #FEE2E2 | #DC2626 | Out of stock, overdue, critical, error |
| **Neutral** | #F3F4F6 | #374151 | Draft, inactive, archived |
| **Dark** | #111827 | #FFFFFF | High-contrast emphasis, count pills |

## **11.1 Badge Specifications**

-   **Padding:** 2px top/bottom, 8px left/right.
-   **Border radius:** 5px (pill-adjacent, not full pill).
-   **Font:** 12px Inter 600, letter-spacing 0.02em.
-   **Count pills:** Use Dark variant (#111827 fill, white text). 18px min-width, 20px height, full border-radius for circular appearance.
-   **Status dot:** 8×8px filled circle. Colour matches the variant fill at 100% opacity (not tinted). Used in notification rows and table status cells.
-   **No custom colours:** Do not create ad-hoc badge colours outside the six defined variants. If a new semantic meaning arises, raise a change request.

# **12\. Components — Notifications**

The notifications page follows the ambient, Google-inspired information architecture defined in the Notifications Redesign Recommendation (February 2026). This section codifies those decisions as system standards.

| **Element** | **Specification** |
| --- | --- |
| **Row height** | 60px default. 64px with two-line description. |
| **Unread indicator** | 8×8px filled circle, colour #1A56DB, left margin 16px. Absent on read. |
| **Source icon** | 40×40px circle. Colour by category (see Colour section). No border, no container. |
| **Title — unread** | 14px Inter 600, #111827 |
| **Title — read** | 14px Inter 400, #6B7280 |
| **Description** | 13px Inter 400, #6B7280. One line max. Truncate with ellipsis. |
| **Timestamp** | 12px Inter 400, #9AA0A6. Right-aligned. '2h ago' &lt; 24h; 'Feb 24' otherwise. |
| **Row hover** | Background #F3F4F6. Three-dot menu fades in at far right. |
| **Three-dot menu items** | Mark as read · Snooze (1h / Tomorrow / Next week) · Go to item · Dismiss |
| **Group header** | 11px Inter 600, all-caps, letter-spacing 0.08em, #9AA0A6. E.g. 'INVENTORY · 3' |
| **Row divider** | 1px solid #E5E7EB |

## **12.1 Toast Notifications**

Transient in-app toasts for action feedback (saved, error, copied, etc.):

-   **Position:** Bottom-right, 24px from edges. Stack upward if multiple toasts appear.
-   **Width:** 320px fixed.
-   **Auto-dismiss:** Success and info toasts: 4 seconds. Warning: 6 seconds. Error: persistent until dismissed.
-   **Actions:** Optional single text action link (e.g. 'Undo') in Blue 600.
-   **Elevation:** Level 4 shadow.

# **13\. Components — Tables**

## **13.1 Data Table Specifications**

-   **Row height:** 48px default (comfortable for operational data). 40px compact (for dense reporting views).
-   **Header row:** Gray 050 background, 13px Inter 600, Gray 700, all-caps, letter-spacing 0.06em. 1px Gray 300 bottom border.
-   **Row divider:** 1px solid Gray 100 (not Gray 300 — hairline only).
-   **Zebra striping:** Optional. Use Gray 050 on odd rows. Do not combine with hover row highlight — choose one.
-   **Hover state:** Gray 100 background on hover row. Reveal row action buttons (three-dot or inline) on hover.
-   **Numeric columns:** Right-aligned. JetBrains Mono Code style. Use consistent decimal places within a column.
-   **Status column:** Badge component. Fixed width column (100px). Centred.
-   **Sortable columns:** Indicate with sort icon (16px, Gray 300 default, Gray 700 active + direction arrow). Click to sort, click again to reverse.
-   **Empty state:** Centred illustration icon (48px, Gray 300) + 'No results' heading + subtext. Never show an empty table shell.
-   **Pagination:** Below table. Ghost button style. Show: 'Showing 1–25 of 142'. Page size selector (25 / 50 / 100).

# **14\. Components — Modals & Dialogs**

## **14.1 Modal Specifications**

-   **Width:** 480px (small), 640px (default), 800px (large), fullscreen (complex forms).
-   **Max height:** 80vh. Overflow scrolls within the modal body, not the header/footer.
-   **Border radius:** 12px.
-   **Overlay:** rgba(0,0,0,0.5) backdrop. Click outside to close (unless form has unsaved changes).
-   **Elevation:** Level 3 shadow.
-   **Header:** 20px Inter 600 title. 24px close (✕) icon button at top right.
-   **Footer:** Right-aligned. Primary action button + Ghost cancel button. 16px gap between.
-   **Focus trap:** Tab cycles only within the open modal. Escape closes (with confirmation if unsaved changes).

## **14.2 Confirmation Dialogs**

For destructive actions (delete, archive, void):

-   **Use the small modal (480px).**
-   **Title states the action: 'Delete product?' not 'Are you sure?'**
-   **Body explains the consequence: 'This will permanently remove \[item\] and cannot be undone.'**
-   **Primary action button uses the Danger variant. Label matches the title verb: 'Delete'.**
-   **Cancel button is Ghost. It is placed to the LEFT of the danger button.**

# **15\. Components — Cards**

## **15.1 Card Specifications**

-   **Border radius:** 8px.
-   **Elevation:** Level 1 shadow by default. Level 2 on hover for interactive cards.
-   **Background:** White (#FFFFFF) or Gray 050 for subtle differentiation.
-   **Border:** 1px solid Gray 300 for non-interactive cards. No border for cards using Level 1+ shadow.
-   **Padding:** 16px (space-4) for standard cards. 24px (space-6) for cards with complex content.
-   **Header:** Optional. 16px bottom padding. Uses Heading 3 style. May include a kebab menu (three-dot) on hover.
-   **Footer:** Optional. 16px top padding, 1px Gray 100 border-top. Contains action buttons (Ghost style, right-aligned).
-   **Empty state:** 80×80px centered icon (Gray 300) + 'No items' heading + subtext description.

## **15.2 Card Usage Rules**

-   **One action per card:** Interactive cards should have one primary action (click anywhere or specific button). Multiple actions belong in a kebab menu.
-   **Consistent width:** Cards in the same grid should have equal height and width. Use flexbox or grid to enforce.
-   **Loading state:** Replace card content with skeleton loader matching the content layout (3 shimmer blocks max).
-   **Hover states:** Only apply to interactive cards (clickable). Informational cards should not have hover effects.

# **16\. Components — Search**

## **16.1 Search Input Specifications**

-   **Height:** 40px for inline search, 48px for search modal input.
-   **Width:** 280px min-width for inline. Full-width for modal.
-   **Background:** White with 1px Gray 300 border.
-   **Focus state:** Blue 600 border, 3px focus ring (0 0 0 3px rgba(26,86,219,0.15)).
-   **Icon:** 20px Lucide Search icon, Gray 500, left-aligned with 12px padding.
-   **Placeholder:** 14px Inter 400, Gray 500. 'Search products, orders, customers...'
-   **Clear button:** 16px X icon, Gray 400, appears on hover/focus when text is present.
-   **Keyboard shortcut:** Ctrl+K / ⌘K opens search modal with focus on input.
-   **Loading state:** 16px spinner icon appears in right side, replacing clear button.

## **16.2 Search Modal Specifications**

-   **Width:** 640px max-width, 90% viewport width.
-   **Max height:** 60vh.
-   **Border radius:** 12px.
-   **Elevation:** Level 3 shadow.
-   **Backdrop:** rgba(0,0,0,0.5) with blur (backdrop-filter: blur(4px)).
-   **Results area:** Scrollable, 320px max-height before scrolling.
-   **Result item:** 48px height, hover Gray 100 background, 8px left border in Blue 600 on hover.
-   **No results state:** Centered 48px icon + 'No results found' + 'Try different keywords' subtext.
-   **Navigation:** Arrow Up/Down to navigate results, Enter to select, Escape to close.

## **16.3 Search Keyboard Shortcuts**

| **Shortcut** | **Action** |
| --- | --- |
| **Ctrl+K / ⌘K** | Open search modal |
| **Escape** | Close search modal |
| **↑ / ↓** | Navigate results |
| **Enter** | Select highlighted result |
| **Tab** | Focus next interactive element |
| **Shift+Tab** | Focus previous interactive element |

# **17\. Components — Tooltips**

## **17.1 Tooltip Specifications**

-   **Trigger:** Hover (desktop) and tap (mobile/touch).
-   **Delay:** 400ms appearance delay. Instant dismissal on mouse leave.
-   **Max width:** 200px.
-   **Padding:** 8px (space-2).
-   **Background:** Gray 900 (#111827) for dark tooltip, White with Level 2 shadow for light tooltip.
-   **Text:** 12px Inter 400, white for dark tooltip, Gray 700 for light tooltip.
-   **Border radius:** 6px.
-   **Arrow:** 8px triangle, centered on tooltip edge (auto-positioned).
-   **Z-index:** 2000 (above all UI elements).
-   **Accessibility:** Use `aria-label` or `title` attribute. Screen readers read the tooltip content.

## **17.2 Tooltip Usage Rules**

-   **Brief content only:** Max 2-3 sentences. Longer content requires a modal or popover.
-   **No interactive elements:** Tooltips cannot contain buttons, links, or form controls.
-   **No HTML formatting:** Plain text only. Use line breaks (\\n) for multi-line tooltips.
-   **Positioning:** Auto-position to avoid clipping. Default to top, fallback to right, bottom, left.
-   **Mobile consideration:** On touch devices, tooltips appear on tap and dismiss on tap outside or after 3 seconds.

# **18\. Components — Tabs & Pills**

## **18.1 Tab Specifications**

-   **Height:** 40px.
-   **Spacing:** 0 horizontal gap (tabs touch each other).
-   **Border bottom:** 2px Gray 300 line spanning full tab container width.
-   **Active state:** Blue 600 2px bottom border, Blue 600 text, Blue 050 background.
-   **Inactive state:** Gray 500 text, no border.
-   **Hover state:** Gray 700 text for inactive tabs.
-   **Padding:** 12px horizontal, 8px vertical.
-   **Font:** 13px Inter 500 (Label style).
-   **Icon:** Optional 16px icon left-aligned with 4px gap from text.
-   **Mobile behavior:** On mobile (< 640px), tabs horizontally scrollable with fade indicators.

## **18.2 Pill Specifications (Filter Chips)**

-   **Height:** 32px.
-   **Border radius:** 16px (full pill).
-   **Background:** Gray 100 for inactive, Blue 600 for active.
-   **Text:** Gray 700 for inactive, White for active.
-   **Border:** 1px Gray 300 for inactive, none for active.
-   **Padding:** 8px horizontal, 6px vertical.
-   **Spacing:** 8px between pills.
-   **Clear button:** Optional X icon (12px) for dismissible filters.
-   **Multi-select:** Pills support multiple active states simultaneously.

## **18.3 Tab/Pill Usage Rules**

-   **One tab active at a time:** Tab navigation is single-select. Pills can be multi-select.
-   **Consistent content area:** Tab content should appear below tabs with no animation (instant switch) for business applications.
-   **Loading state:** Show skeleton loader in tab content area while loading, not on tab itself.
-   **Accessibility:** Use `role="tablist"`, `role="tab"`, `role="tabpanel"`. Arrow keys navigate tabs. Enter/Space activates.

# **19\. Components — Navigation**

## **19.1 Top Navigation Bar**

-   **Height:** 64px. Full-width. White background. 1px Gray 200 bottom border.
-   **Left:** Logo mark (32px) + wordmark. Clickable, links to Dashboard.
-   **Centre:** Global search input (see §16 Components — Search). Triggered by Ctrl+K / ⌘K.
-   **Right:** Notification bell (with count badge) · Settings icon · User avatar (40px circle, initials fallback).

## **19.2 Sidebar Navigation**

-   **Expanded width:** 240px. Collapsed width: 64px (icon only).
-   **Nav item height:** 40px. 12px horizontal padding. 8px vertical padding.
-   **Active state:** Blue 050 background, Blue 600 left border (3px), Blue 600 text and icon.
-   **Hover state:** Gray 050 background.
-   **Section headers:** 11px Inter 600 all-caps, Gray 400, 16px top margin. Not clickable.
-   **Collapse trigger:** Icon-only button at bottom of sidebar. Persists state in localStorage.
-   **Upgrade prompt:** If applicable, pin to bottom above the user section. Use a subtle Blue 050 card, never an alarming banner.

# **20\. Accessibility**

ifinmail targets WCAG 2.1 Level AA compliance across all interfaces. Accessibility is not a post-ship audit — it is a design and build requirement checked during component review.

| **Requirement** | **Standard** | **Implementation** |
| --- | --- | --- |
| **Colour contrast — body text** | WCAG AA 4.5:1 | Gray 700 (#374151) on white = 8.6:1 ✓ |
| **Colour contrast — large text** | WCAG AA 3:1 | Gray 500 (#6B7280) on white = 4.6:1 ✓ |
| **Colour contrast — UI components** | WCAG AA 3:1 | Blue 600 (#1A56DB) borders on white = 4.5:1 ✓ |
| **Focus ring** | WCAG 2.1 §2.4.7 | 3px #1A56DB ring on all interactive elements |
| **Touch target** | WCAG 2.5.5 | Minimum 44×44px for all tappable elements |
| **Keyboard navigation** | WCAG 2.1 §2.1.1 | All actions reachable via Tab, Enter, Escape, Arrows |
| **Screen reader labels** | WCAG 2.1 §4.1.2 | aria-label on icon-only buttons; role=dialog on modals |
| **Error identification** | WCAG 2.1 §3.3.1 | Errors shown as text + red border (never colour only) |
| **Skip navigation** | WCAG 2.4.1 | Skip-to-content link at top of every page |
| **Reduced motion** | WCAG 2.3.3 | @media (prefers-reduced-motion) disables transitions |

## **20.1 Testing Requirements**

-   **Automated:** Run axe-core or Lighthouse accessibility audit on every page before merge. Zero critical violations permitted.
-   **Keyboard test:** Every user flow must be completable using keyboard only (Tab, Shift+Tab, Enter, Escape, Arrow keys). Document keyboard shortcuts for power user features.
-   **Screen reader:** Test critical flows (login, create product, view notifications) with VoiceOver (macOS) and NVDA (Windows) on each major release.
-   **Zoom test:** All layouts must remain functional at 200% browser zoom without horizontal scrolling.

# **21\. Do / Don't**

| **✓ DO** | **✗ DON'T** |
| --- | --- |
| Use Inter for all UI text | Use system fonts or other sans-serif alternatives |
| Use a single Primary button per screen | Stack two or more Primary (blue-fill) buttons in one view |
| Pair all colour states with a text label or icon | Use colour as the sole indicator of state or error |
| Show action menus on hover (three-dot) | Place all possible actions as permanent visible buttons on rows |
| Use flat rows for notification and list items | Wrap every list item in a rounded, bordered card |
| Reserve red for destructive/critical actions only | Use red for decorative accents or category labels |
| Show 8–10 list items per viewport | Use 100–110px card rows that show only 3 items above the fold |
| Anchor the cancel button to the LEFT of the primary action | Place cancel to the right of the danger button |
| Use JetBrains Mono for all numeric values | Display stock counts, prices, or percentages in Inter |
| Confirm destructive actions with a dialog stating the exact consequence | Use vague copy like 'Are you sure you want to do this?' |
| Group notifications by source category | Sort notifications by time only with no grouping |
| Animate only functional state changes | Add entrance animations to every list item on every page load |
| Constrain text columns to 60–80 character line length | Allow text to span full 1280px width |
| Use skeleton loading screens for content over 300ms | Use full-page spinners for content loading |

# **22\. Governance & Change Process**

## **22.1 How to Use This Document**

This design guide is the single source of truth for all design decisions in the ifinmail platform. When building a new feature or component:

1.  **Check this guide first.** If the pattern you need is defined, use it exactly as specified.
2.  **If the pattern is missing,** create it using the principles and tokens in this guide, then submit it for review.
3.  **If the existing pattern needs to change,** raise a Change Request (see 18.3). Do not diverge unilaterally.

## **22.2 Review Cadence**

-   **Quarterly full review:** The Design lead audits the entire guide every quarter. New patterns added during the quarter are reviewed, documented, or deprecated.
-   **Triggered review:** Any new product surface, major refactor, or significant user research finding triggers an immediate focused review of the relevant sections.
-   **Version history:** All changes are logged with version number, date, author, and a one-line description of the change.

## **22.3 Change Request Process**

To propose a change to this design system:

1.  Document the existing pattern and the proposed change.
2.  Include the rationale — user research, accessibility requirement, or new product need.
3.  Show before/after examples.
4.  Identify all surfaces and components affected by the change.
5.  Submit to the Design lead. Changes affecting more than 3 components require a team review session.

*Breaking changes — those that require updating existing components across the system — require a migration plan specifying which views are affected and a ship timeline for the update.*

## **22.4 Browser Support Matrix**

The ifinmail platform supports the following browsers. All components must be tested and functional across this matrix.

| **Browser** | **Minimum Version** | **Support Status** | **Notes** |
| --- | --- | --- | --- |
| **Chrome** | 90+ | Full Support | Primary development target |
| **Firefox** | 88+ | Full Support | All features supported |
| **Safari** | 14+ | Full Support | macOS and iOS |
| **Edge** | 90+ | Full Support | Chromium-based |
| **Mobile Safari** | iOS 14+ | Full Support | iPhone/iPad testing required |
| **Chrome Mobile** | Android 10+ | Full Support | Android testing required |

### Browser Support Requirements

- **Graceful degradation:** Features not supported in older browsers must degrade gracefully without breaking core functionality
- **CSS fallbacks:** Provide fallback values for modern CSS features (CSS Grid, Flexbox, custom properties)
- **JavaScript polyfills:** Only add polyfills for critical features affecting core user flows
- **Testing cadence:** Test all supported browsers quarterly or after major feature releases
- **Deprecation notice:** Browser version support can only be dropped after one-quarter advance notice and migration guidance

### Progressive Enhancement Strategy

The ifinmail platform follows a progressive enhancement approach:

1. **Core functionality** must work in all supported browsers without JavaScript
2. **Enhanced experiences** (animations, advanced interactions) layer on top progressively
3. **Feature detection** is preferred over browser detection
4. **No critical features** depend on cutting-edge browser APIs

## **22.5 Internationalization (i18n) Guidelines**

The ifinmail platform supports multiple languages and must be designed for international users from the ground up.

### Text Length Considerations

- **Text expansion:** Design for 30-50% text expansion in non-English languages
- **RTL support:** All layouts must support right-to-left (RTL) languages (Arabic, Hebrew)
- **Line breaking:** Allow text containers to wrap naturally without fixed widths
- **Truncation:** Truncate with ellipsis only where context is clear, otherwise allow full text expansion

### Typography for Internationalization

- **Font fallback:** Specify font stacks that support required character sets
- **Line height:** Use generous line height (minimum 1.5) for languages with complex scripts
- **Font size:** Avoid font sizes below 12px even for dense information displays
- **Character spacing:** Avoid tight letter-spacing which can cause character overlap in some languages

### Layout and Spacing

- **Fixed widths avoided:** Never use fixed pixel widths for text containers
- **Flexible spacing:** Use percentage-based or flexible spacing units (rem, em, %)
- **Direction-aware layouts:** All layouts must adapt to LTR (left-to-right) and RTL direction
- **Icon positioning:** Icon placement must respect text direction (left/right alignment)

### Date, Time, and Numbers

- **Locale-aware formatting:** Use browser/locale-aware formatting for dates and times
- **Number formatting:** Respect locale-specific number formats (decimal separators, thousands separators)
- **Currency:** Display currency symbols and placement according to locale
- **Time zones:** Always display times in user's local timezone with UTC reference

### Implementation Example

```html
<!-- Direction-aware markup -->
<html lang="en" dir="ltr">
<!-- RTL language example -->
<html lang="ar" dir="rtl">
```

```css
/* Direction-aware CSS */
[dir="rtl"] .ifinmail-nav-item {
  padding-left: 12px;
  padding-right: 0;
  border-right: 3px solid var(--ifinmail-color-primary);
  border-left: none;
}

[dir="ltr"] .ifinmail-nav-item {
  padding-right: 12px;
  padding-left: 0;
  border-left: 3px solid var(--ifinmail-color-primary);
  border-right: none;
}
```

### i18n Testing Requirements

- **Language coverage:** Test with at least three different languages covering different text expansion scenarios
- **RTL testing:** Test Arabic or Hebrew to verify RTL layout integrity
- **Character encoding:** Ensure UTF-8 encoding throughout the application
- **Input methods:** Test with different keyboard layouts and input method editors (IMEs)

# **23\. CSS Implementation Standards**

All design tokens defined in this guide are implemented in code through a single centralised file: variables.css. All CSS classes and custom properties across the ifinmail platform use the ifinmail- prefix. This ensures zero collision with third-party libraries, makes every design-system class immediately identifiable in a codebase, and makes global search across files reliable.

*Rule: Never hardcode a colour, spacing value, font size, or shadow in a component stylesheet. Every value must reference a variable from variables.css.*

## **23.1 variables.css — The Single Source of Truth**

The file is structured into named sections that mirror this design guide exactly. Each section maps directly to a chapter above. Variable names follow the pattern: --ifinmail-{category}-{token}.

**variables.css file structure**

/\* ═══════════════════════════════════════════

ifinmail Design System — variables.css

Single source of truth for all design tokens.

v1.1 — April 2026

═══════════════════════════════════════════ \*/

:root {

/\* §3 Colour \*/

\--ifinmail-color-primary: #1A56DB;

\--ifinmail-color-primary-hover: #3B6FE8;

\--ifinmail-color-primary-tint: #E8F0FE;

\--ifinmail-color-danger: #DC2626;

\--ifinmail-color-danger-tint: #FEE2E2;

\--ifinmail-color-warning: #D97706;

\--ifinmail-color-warning-tint: #FEF3C7;

\--ifinmail-color-success: #059669;

\--ifinmail-color-success-tint: #D1FAE5;

\--ifinmail-color-text-primary: #111827;

\--ifinmail-color-text-secondary: #374151;

\--ifinmail-color-text-muted: #6B7280;

\--ifinmail-color-border: #E5E7EB;

\--ifinmail-color-surface-1: #F9FAFB;

\--ifinmail-color-surface-2: #F3F4F6;

/\* §3 Colour — Dark Mode \*/

@media (prefers-color-scheme: dark) {

  :root {

    \--ifinmail-color-primary: #3B82F6;

    \--ifinmail-color-primary-hover: #60A5FA;

    \--ifinmail-color-primary-tint: #1E3A8A;

    \--ifinmail-color-danger: #EF4444;

    \--ifinmail-color-danger-tint: #7F1D1D;

    \--ifinmail-color-warning: #F59E0B;

    \--ifinmail-color-warning-tint: #78350F;

    \--ifinmail-color-success: #10B981;

    \--ifinmail-color-success-tint: #064E3B;

    \--ifinmail-color-text-primary: #F9FAFB;

    \--ifinmail-color-text-secondary: #D1D5DB;

    \--ifinmail-color-text-muted: #9CA3AF;

    \--ifinmail-color-border: #4B5563;

    \--ifinmail-color-surface-1: #111827;

    \--ifinmail-color-surface-2: #1F2937;

  }

}

/\* §4 Typography \*/

\--ifinmail-font-ui: 'Inter', sans-serif;

\--ifinmail-font-mono: 'JetBrains Mono', monospace;

\--ifinmail-text-display: 700 30px/1.2 var(--ifinmail-font-ui);

\--ifinmail-text-h1: 600 24px/1.3 var(--ifinmail-font-ui);

\--ifinmail-text-body: 400 14px/1.5 var(--ifinmail-font-ui);

\--ifinmail-text-caption: 400 12px/1.4 var(--ifinmail-font-ui);

/\* §5 Spacing \*/

\--ifinmail-space-1: 4px; --ifinmail-space-2: 8px; --ifinmail-space-3: 12px;

\--ifinmail-space-4: 16px; --ifinmail-space-6: 24px; --ifinmail-space-8: 32px;

\--ifinmail-space-12: 48px; --ifinmail-space-16: 64px;

/\* §6 Elevation \*/

\--ifinmail-shadow-1: 0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06);

\--ifinmail-shadow-2: 0 4px 12px rgba(0,0,0,.10), 0 2px 4px rgba(0,0,0,.06);

\--ifinmail-shadow-3: 0 8px 24px rgba(0,0,0,.12), 0 4px 8px rgba(0,0,0,.08);

\--ifinmail-shadow-4: 0 16px 40px rgba(0,0,0,.16), 0 6px 12px rgba(0,0,0,.10);

/\* §8 Motion \*/

\--ifinmail-duration-fast: 100ms;

\--ifinmail-duration-normal: 180ms;

\--ifinmail-duration-slow: 280ms;

\--ifinmail-easing-standard: cubic-bezier(.4, 0, .2, 1);

}

## **23.2 CSS Class Naming Convention**

All CSS classes follow the pattern: ifinmail-{component}\_\_{element}--{modifier} (BEM-style with the mandatory prefix). The ifinmail- prefix is always present — even on base component classes.

**Class name examples by component**

| **Context** | **Class Name** | **Notes** |
| --- | --- | --- |
| **Button — base** | .ifinmail-btn | Base class, always present |
| **Button — variant** | .ifinmail-btn--primary | Also: --secondary, --ghost, --danger |
| **Button — size** | .ifinmail-btn--sm / --lg | Default (md) needs no modifier |
| **Input — base** | .ifinmail-input | Also used for select, textarea |
| **Input — state** | .ifinmail-input--error | Also: --disabled. Focus via :focus-visible |
| **Badge — variant** | .ifinmail-badge--warning | Also: --success, --danger, --info, --neutral |
| **Notification row** | .ifinmail-notif-row | + --unread modifier for bold/dot state |
| **Table row — state** | .ifinmail-table__row--selected | BEM __element + --modifier |
| **Modal** | .ifinmail-modal__header | Also: __body, __footer, __close |
| **Utility — layout** | .ifinmail-sr-only | Screen-reader-only visually hidden text |

## **23.3 Naming Rules & Enforcement**

-   **The prefix is mandatory without exception:** Even utility and layout classes use the prefix. There are no unprefixed classes anywhere in the codebase.
-   **No hardcoded values in component CSS:** All values must reference var(--ifinmail-\*). A linting rule enforces this on CI.
-   **variables.css is imported once globally:** It is the first stylesheet loaded. Component stylesheets never re-declare token values.
-   **Adding a new token requires a design system change request:** Do not add new --ifinmail-\* variables to variables.css without a corresponding update to this design guide (see §18.3).
-   **Deprecated tokens stay in variables.css for one release:** Mark them with a comment. Remove only once all references are migrated.
-   **Class names are kebab-case only:** No camelCase or snake\_case in class names. Use ifinmail-notif-row, not ifinmailNotifRow.

## **23.4 CSS File Organisation**

The stylesheet directory structure mirrors this design guide. Each section has a corresponding file, all imported via a single main.css.

**Directory structure**

```
styles/
├── variables.css ← all tokens (§3–§8)
├── reset.css ← box-sizing, margin resets
├── typography.css ← .ifinmail-text-* utilities (§4)
├── layout.css ← grid, spacing utilities (§5)
├── components/
│   ├── ifinmail-btn.css
│   ├── ifinmail-input.css
│   ├── ifinmail-badge.css
│   ├── ifinmail-modal.css
│   ├── ifinmail-notif.css
│   └── ifinmail-table.css
└── main.css ← @import order: variables → reset → typography → layout → components
```

*Never import variables.css inside a component stylesheet. It must only be imported at the global entry point to guarantee the tokens are available before any component styles are parsed.*

## **23.5 Component Code Examples**

### Button Component

```html
<!-- Primary Button -->
<button class="ifinmail-btn ifinmail-btn--primary">
  Save Changes
</button>

<!-- Secondary Button -->
<button class="ifinmail-btn ifinmail-btn--secondary">
  Cancel
</button>

<!-- Ghost Button with Icon -->
<button class="ifinmail-btn ifinmail-btn--ghost">
  <svg class="ifinmail-btn__icon" width="16" height="16">
    <!-- Lucide icon content -->
  </svg>
  Edit
</button>

<!-- Danger Button -->
<button class="ifinmail-btn ifinmail-btn--danger">
  Delete
</button>

<!-- Disabled Button -->
<button class="ifinmail-btn" disabled>
  Processing...
</button>
```

```css
.ifinmail-btn {
  height: 40px;
  padding: 0 var(--ifinmail-space-4);
  border-radius: 8px;
  font-family: var(--ifinmail-font-ui);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--ifinmail-duration-fast) ease-out;
}

.ifinmail-btn--primary {
  background: var(--ifinmail-color-primary);
  color: white;
  border: none;
}

.ifinmail-btn--primary:hover {
  background: var(--ifinmail-color-primary-hover);
}

.ifinmail-btn--secondary {
  background: white;
  color: var(--ifinmail-color-primary);
  border: 1px solid var(--ifinmail-color-primary);
}

.ifinmail-btn--ghost {
  background: white;
  color: var(--ifinmail-color-text-secondary);
  border: 1px solid var(--ifinmail-color-border);
}

.ifinmail-btn--danger {
  background: var(--ifinmail-color-danger);
  color: white;
  border: none;
}

.ifinmail-btn__icon {
  width: 16px;
  height: 16px;
  margin-right: var(--ifinmail-space-1);
}
```

### Form Input Component

```html
<!-- Text Input -->
<div class="ifinmail-form-group">
  <label class="ifinmail-label" for="product-name">
    Product Name <span class="ifinmail-label__required">*</span>
  </label>
  <input
    type="text"
    id="product-name"
    class="ifinmail-input"
    placeholder="Enter product name"
    required
  >
  <p class="ifinmail-helper-text">
    This name will appear in your catalog.
  </p>
</div>

<!-- Input with Error State -->
<div class="ifinmail-form-group ifinmail-form-group--error">
  <label class="ifinmail-label" for="product-sku">
    SKU <span class="ifinmail-label__required">*</span>
  </label>
  <input
    type="text"
    id="product-sku"
    class="ifinmail-input ifinmail-input--error"
    value="INVALID-@#SKU"
    required
  >
  <p class="ifinmail-error-text">
    SKU must contain only letters, numbers, and hyphens.
  </p>
</div>
```

```css
.ifinmail-form-group {
  margin-bottom: var(--ifinmail-space-4);
}

.ifinmail-label {
  display: block;
  font-family: var(--ifinmail-font-ui);
  font-size: 13px;
  font-weight: 500;
  color: var(--ifinmail-color-text-secondary);
  margin-bottom: var(--ifinmail-space-1);
}

.ifinmail-label__required {
  color: var(--ifinmail-color-danger);
}

.ifinmail-input {
  width: 100%;
  height: 40px;
  padding: var(--ifinmail-space-2) var(--ifinmail-space-3);
  border: 1px solid var(--ifinmail-color-border);
  border-radius: 8px;
  background: white;
  font-family: var(--ifinmail-font-ui);
  font-size: 14px;
  transition: all var(--ifinmail-duration-fast) ease-out;
}

.ifinmail-input:focus {
  outline: none;
  border-color: var(--ifinmail-color-primary);
  box-shadow: 0 0 0 3px rgba(26,86,219,0.15);
}

.ifinmail-input--error {
  border-color: var(--ifinmail-color-danger);
}

.ifinmail-input--error:focus {
  box-shadow: 0 0 0 3px rgba(220,38,38,0.12);
}

.ifinmail-helper-text {
  margin-top: var(--ifinmail-space-1);
  font-size: 12px;
  color: var(--ifinmail-color-text-muted);
}

.ifinmail-error-text {
  margin-top: var(--ifinmail-space-1);
  font-size: 12px;
  color: var(--ifinmail-color-danger);
}
```

### Badge Component

```html
<!-- Info Badge -->
<span class="ifinmail-badge ifinmail-badge--info">
  3 Unread
</span>

<!-- Success Badge -->
<span class="ifinmail-badge ifinmail-badge--success">
  Active
</span>

<!-- Warning Badge -->
<span class="ifinmail-badge ifinmail-badge--warning">
  Low Stock
</span>

<!-- Danger Badge -->
<span class="ifinmail-badge ifinmail-badge--danger">
  Critical
</span>

<!-- Neutral Badge -->
<span class="ifinmail-badge ifinmail-badge--neutral">
  Draft
</span>

<!-- Dark Count Pill -->
<span class="ifinmail-badge ifinmail-badge--dark">
  42
</span>
```

```css
.ifinmail-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--ifinmail-space-2);
  border-radius: 5px;
  font-family: var(--ifinmail-font-ui);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.ifinmail-badge--info {
  background: var(--ifinmail-color-primary-tint);
  color: var(--ifinmail-color-primary);
}

.ifinmail-badge--success {
  background: var(--ifinmail-color-success-tint);
  color: var(--ifinmail-color-success);
}

.ifinmail-badge--warning {
  background: var(--ifinmail-color-warning-tint);
  color: var(--ifinmail-color-warning);
}

.ifinmail-badge--danger {
  background: var(--ifinmail-color-danger-tint);
  color: var(--ifinmail-color-danger);
}

.ifinmail-badge--neutral {
  background: var(--ifinmail-color-surface-2);
  color: var(--ifinmail-color-text-secondary);
}

.ifinmail-badge--dark {
  background: var(--ifinmail-color-text-primary);
  color: white;
  min-width: 18px;
  justify-content: center;
  height: 20px;
  border-radius: 10px;
}
```

### Modal Component

```html
<div class="ifinmail-modal">
  <div class="ifinmail-modal__overlay"></div>
  <div class="ifinmail-modal__container">
    <div class="ifinmail-modal__header">
      <h2 class="ifinmail-modal__title">Edit Product</h2>
      <button class="ifinmail-modal__close" aria-label="Close">
        <svg width="24" height="24"><!-- Lucide X icon --></svg>
      </button>
    </div>
    <div class="ifinmail-modal__body">
      <!-- Modal content here -->
    </div>
    <div class="ifinmail-modal__footer">
      <button class="ifinmail-btn ifinmail-btn--ghost">Cancel</button>
      <button class="ifinmail-btn ifinmail-btn--primary">Save Changes</button>
    </div>
  </div>
</div>
```

```css
.ifinmail-modal {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ifinmail-modal__overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
}

.ifinmail-modal__container {
  position: relative;
  background: white;
  border-radius: 12px;
  max-width: 640px;
  width: 90%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--ifinmail-shadow-3);
}

.ifinmail-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ifinmail-space-4);
  border-bottom: 1px solid var(--ifinmail-color-border);
}

.ifinmail-modal__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--ifinmail-color-text-primary);
}

.ifinmail-modal__close {
  background: none;
  border: none;
  cursor: pointer;
  padding: var(--ifinmail-space-1);
  border-radius: 4px;
}

.ifinmail-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--ifinmail-space-4);
}

.ifinmail-modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--ifinmail-space-4);
  padding: var(--ifinmail-space-4);
  border-top: 1px solid var(--ifinmail-color-border);
}
```

## **23.6 Performance Guidelines**

Performance is a design principle that affects user experience. All components must meet performance standards while maintaining design fidelity.

### Animation Performance Requirements

- **60fps target:** All animations must maintain 60 frames per second
- **GPU acceleration:** Use CSS transforms (translate, scale, rotate) and opacity for animations - avoid animating layout properties (width, height, margin, padding)
- **Batched animations:** Multiple simultaneous animations should be batched using CSS animations or JavaScript requestAnimationFrame
- **Reduced motion:** Always respect `@media (prefers-reduced-motion)` - disable non-essential animations

### Performance Budgets

| **Resource Type** | **Budget** | **Notes** |
| --- | --- | --- |
| **Initial HTML** | 15KB gzipped | Critical path content only |
| **Critical CSS** | 50KB gzipped | Above-the-fold styles only |
| **JavaScript** | 200KB gzipped per route | Route-specific bundles preferred |
| **Images** | 1MB total per page | Lazy load below-fold images |
| **Total page weight** | 3MB maximum | Including all resources |

### Optimization Techniques

- **Lazy loading:** Implement intersection observer for images and components below viewport
- **Code splitting:** Split JavaScript bundles by route and feature
- **Tree shaking:** Remove unused CSS and JavaScript in production builds
- **Font optimization:** Subset web fonts to include only used characters
- **Image optimization:** Serve modern formats (WebP) with fallbacks, use responsive images
- **Defer non-critical JavaScript:** Load analytics and tracking scripts after page becomes interactive

### Performance Monitoring

- **Lighthouse scores:** Target 90+ for Performance, Accessibility, Best Practices
- **Core Web Vitals:** Monitor LCP, FID, CLS against recommended thresholds
- **Bundle analysis:** Review bundle sizes weekly, identify and remove unused dependencies
- **Performance budgets:** Configure build tools to fail if budgets are exceeded

### CSS Performance Best Practices

- **Selector efficiency:** Avoid deep nesting (>3 levels) and universal selectors
- **CSS containment:** Use `contain` property where appropriate to isolate layout recalculations
- **Will-change hint:** Use `will-change` sparingly and only for frequently animated properties
- **Avoid expensive properties:** Minimize use of `box-shadow`, `filter`, and `border-radius` on large elements

## **23.7 Linting and Quality Control**

Automated quality control ensures design system consistency across the codebase. All projects must implement the following linting rules.

### CSS Linting Configuration

Use Stylelint with the following configuration:

```json
{
  "extends": [
    "stylelint-config-standard"
  ],
  "rules": {
    "selector-class-pattern": "^(ifinmail-[a-z][a-z0-9]*)(--[a-z][a-z0-9]*)?(__[a-z][a-z0-9]*)?$",
    "declaration-property-value-no-unknown": true,
    "color-named": "never",
    "font-family-no-duplicate-names": true,
    "function-url-quotes": "always",
    "value-keyword-case": "lower",
    "property-no-vendor-prefix": true,
    "selector-no-vendor-prefix": true,
    "declaration-no-important": true,
    "max-nesting-depth": 3
  },
  "overrides": [
    {
      "files": ["variables.css"],
      "rules": {
        "selector-class-pattern": null
      }
    }
  ]
}
```

### Design Token Validation

Automated check to prevent hardcoded values:

```javascript
// Custom ESLint rule for design token usage
const disallowedPatterns = [
  /#[0-9A-Fa-f]{6}/, // Hex colors
  /\d+px(?!\w)/, // Pixel values except in variables.css
  /\d+rem(?!\w)/, // Rem values except in variables.css
];

module.exports = {
  rules: {
    "no-hardcoded-design-values": {
      meta: {
        type: "problem",
        docs: {
          description: "Prevent hardcoded design values in component CSS",
        },
      },
      create: (context) => ({
        Property(node) {
          const value = node.value;
          const filename = context.getFilename();

          // Allow hardcoded values in variables.css
          if (filename.includes("variables.css")) return;

          disallowedPatterns.forEach((pattern) => {
            if (pattern.test(value)) {
              context.report({
                node,
                message: `Hardcoded design value "${value}" found. Use a design token variable instead.`,
              });
            }
          });
        },
      }),
    },
  },
};
```

### Component Validation Checklist

All components must pass the following validation before merge:

- **[ ]** All classes use `ifinmail-` prefix
- **[ ]** No hardcoded colors, spacing, font sizes, or shadows
- **[ ]** Accessibility requirements met (WCAG AA contrast, ARIA labels)
- **[ ]** Keyboard navigation works (Tab, Enter, Escape, Arrow keys)
- **[ ]** Screen reader tested (VoiceOver/NVDA)
- **[ ]** Responsive behavior verified (mobile, tablet, desktop)
- **[ ]** Dark mode compatible (colors maintain contrast)
- **[ ]** Performance within budget (Lighthouse 90+)
- **[ ]** RTL layout support verified (for internationalization)
- **[ ]** No console errors or warnings

### Pre-commit Hooks

Implement repository-native pre-commit hooks to catch design system violations early without depending on Node-based tooling:

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for hardcoded values in new CSS files
git diff --cached --name-only | grep '\.css$' | xargs grep -n '#[0-9A-Fa-f]\|px\|rem' | grep -v variables.css

# Exit with error if violations found
if [ $? -eq 0 ]; then
  echo "❌ Design system violations found. Please fix hardcoded values."
  exit 1
fi

echo "✅ Design system validation passed"
```

## **23.8 Measurement Unit Guidelines**

The ifinmail design system uses a consistent approach to measurement units to ensure scalability and maintainability.

### When to Use `rem` Units

Use `rem` (root em) for:
- **Typography:** Font sizes, line heights
- **Spacing:** Component padding, margins where relative to base font size
- **Responsive spacing:** Layout spacing that should scale with user's base font size

```css
.ifinmail-text-body {
  font-size: 0.875rem; /* 14px based on 16px root */
  line-height: 1.5rem;
}

.ifinmail-card {
  padding: 1.5rem; /* Scales with user's font size settings */
}
```

### When to Use `px` Units

Use `px` (pixels) for:
- **Border widths:** 1px borders for crisp rendering
- **Border radius:** Fixed radius values for consistent rounded corners
- **Minimum dimensions:** Heights, widths where precision matters
- **Shadows:** Fixed shadow offsets and blur values
- **Icon sizes:** Consistent icon dimensions across components

```css
.ifinmail-input {
  border: 1px solid var(--ifinmail-color-border); /* 1px always 1px */
  border-radius: 8px; /* Consistent 8px corners */
  height: 40px; /* Precise 40px height */
  box-shadow: 0 1px 3px rgba(0,0,0,0.08); /* Fixed shadow values */
}

.ifinmail-icon {
  width: 24px; /* Consistent 24px icons */
  height: 24px;
}
```

### When to Use `%` Units

Use `%` (percentage) for:
- **Responsive widths:** Layout widths that should adapt to container
- **Flex basis:** Flexible sizing in flexbox layouts
- **Media queries:** Breakpoints for responsive design

```css
.ifinmail-modal__container {
  width: 90%; /* 90% of container width */
  max-width: 640px; /* But never exceed 640px */
}

@media (min-width: 768px) {
  .ifinmail-layout {
    flex-direction: row; /* 768px breakpoint */
  }
}
```

### When to Use `em` Units

Use `em` (element em) for:
- **Component-relative spacing:** Spacing relative to component's own font size
- **Icon sizing relative to text:** Icons that should scale with surrounding text

```css
.ifinmail-icon--inline {
  width: 1em; /* Scales with parent font size */
  height: 1em;
}
```

### Unit Selection Rationale

- **`rem` for accessibility:** Scales with user's browser font size settings
- **`px` for precision:** Where exact pixel values matter for design fidelity
- **`%` for responsiveness:** Flexible layouts that adapt to viewport
- **`em` for component context:** Spacing relative to component's own typography

**Rule of Thumb:** Use `rem` for typography and spacing that should scale, `px` for borders, borders-radius, and fixed dimensions, `%` for responsive layouts, and `em` only when specifically needed for element-relative scaling.

*ifinmail Design System v1.1 · Product & Design Team · April 2026*

# **24\. Cross-Reference Documentation**

This design system references and aligns with other project documentation. Maintain consistency across all documents.

## **24.1 Related Design Documents**

The following design documents contain detailed recommendations that inform this design system:

### Current Recommendations

- **Notifications Redesign Recommendation (February 2026)**
  - Defines the ambient, Google-inspired information architecture
  - Referenced in: §12 Components — Notifications
  - Status: Implemented, codified in this design system

- **Search Redesign Recommendation (February 2026)**
  - Establishes search modal standards and keyboard shortcuts
  - Referenced in: §16 Components — Search
  - Status: Implemented, search modal triggered by Ctrl+K / ⌘K

### Project Documentation

- **ifinmail Design System v0.0.1** (current document)
  - Primary design system documentation
  - Updated: February 2026
  - Status: Active — Mandatory for all new work

### Architecture Documentation

- **Settings Ownership Architecture** (`docs/settings-ownership-architecture.md`)
  - Defines ownership boundaries for settings across platform
  - Referenced in: Component design for settings interfaces
  - Status: Active — Guides settings-related component design

- **Settings Segmentation Alignment Proposal** (`docs/settings-segmentation-alignment-proposal.md`)
  - Proposed improvements to settings organization
  - Referenced in: Navigation component design considerations
  - Status: Under review — may impact sidebar navigation design

### Business Context Documentation

- **Platform Users Ecosystem** (`docs/platform-users-ecosystem.md`)
  - Defines user types, permissions, and access patterns
  - Referenced in: Navigation, permissions-aware component design
  - Status: Active — informs component permission handling

- **CES Optimization Proposal - Business Settings** (`docs/ces-optimization-proposal-business-settings.md`)
  - User experience improvements for business settings
  - Referenced in: Settings form component design
  - Status: Under review — may impact form input patterns

## **24.2 Design System Integration**

### Component Library Dependencies

- **Lucide Icons v0.400+:** Primary icon library (24px grid, 1.5px stroke)
  - Documentation: https://lucide.dev/
  - Integration: Referenced in §7 Iconography
  - Usage: All UI icons throughout platform

- **Inter Font:** Primary UI font family
  - Documentation: https://rsms.me/inter/
  - Integration: Referenced in §4 Typography
  - Usage: All body text, headings, labels

- **JetBrains Mono:** Monospace font for numeric data and code
  - Documentation: https://www.jetbrains.com/lp/mono/
  - Integration: Referenced in §4 Typography
  - Usage: Numbers, prices, stock values, code snippets

### Design Tools Integration

- **Stitch Design System:** Design tool for creating and managing components
  - Referenced in: Component development workflow
  - Usage: Visual component design and prototyping

- **Figma:** Collaborative design tool (if used)
  - Integration: Design mockups and prototyping
  - Usage: Component visual design and user testing

## **24.3 Cross-Reference Maintenance**

### Update Coordination

When updating this design system, check for impact on related documents:

1. **Review related documents** for references to changing patterns
2. **Update cross-references** when sections move or are renumbered
3. **Communicate changes** to teams maintaining related documentation
4. **Version alignment** - maintain consistent version numbers across design system and related documents

### Document Sync Process

- **Quarterly review:** All design-related documents reviewed together
- **Change propagation:** Design system changes communicated to document maintainers
- **Version coordination:** Major design system updates trigger related document reviews
- **Conflict resolution:** Design system is authoritative - related documents must align

### Reference Format

When referencing this design system from other documents:

```markdown
See DESIGN.md §4 Typography for font specifications
Refer to DESIGN.md §9.1 Button Specifications for implementation details
Follow DESIGN.md §3.2 Dark Mode Token Mappings for theme support
```

### Broken Reference Prevention

- **Section renumbering:** When sections are renumbered, search for cross-references
- **Pattern deprecation:** Document deprecation in related documents before removal
- **New patterns:** Announce new patterns to maintainers of related documents
- **Documentation migration:** Update internal documentation when design system patterns change

## **24.4 Future Document Roadmap**

### Planned Documentation

- **Mobile Design Supplement:** Specific considerations for mobile interfaces
- **Dark Theme Supplement:** Deep dive into dark mode implementation patterns
- **Component Interaction Guide:** Detailed interaction patterns and user flows
- **Accessibility Testing Handbook:** Step-by-step accessibility testing procedures
- **Internationalization Guide:** Detailed i18n implementation patterns and testing

### Document Priorities

1. **Mobile Design Supplement** - Medium priority (current focus is web)
2. **Dark Theme Supplement** - High priority (basic tokens implemented, detailed patterns needed)
3. **Component Interaction Guide** - Medium priority (patterns exist in sections, need consolidation)
4. **Accessibility Testing Handbook** - High priority (testing requirements defined, detailed guide needed)
5. **Internationalization Guide** - High priority (basic guidelines in §18.5, comprehensive guide needed)

### Document Governance

- **Document ownership:** Each document has assigned maintainer(s)
- **Review cadence:** Documents reviewed quarterly or after major platform changes
- **Version alignment:** Design system version informs related document versions
- **Change coordination:** Major changes coordinated across design system and related documents

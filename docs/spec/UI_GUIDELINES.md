# UI_GUIDELINES

# HT Lens UI & UX Guidelines

## Vision

HT Lens should feel like a professional analytics platform: fast, clean, information-dense, and intuitive.

## Design Principles

- Clarity over decoration
- Data-first dashboards
- Consistent interactions
- Responsive layouts
- Accessibility by default

## Technology

- React
- TypeScript
- Tailwind CSS
- ECharts

## Layout

- Persistent left navigation
- Top application bar
- Breadcrumbs
- Responsive content area
- Right-side contextual panel (optional)

## Navigation

Primary modules:
- Dashboard
- Team
- Matches
- League
- Training
- Economy
- Stadium
- Youth
- Transfers
- Settings

## Tables

All tables should support:

- Sorting
- Filtering
- Multi-column filters
- Pagination
- Sticky headers
- Column selector
- CSV export
- Keyboard navigation

## Charts

Preferred library:

ECharts

Supported visualizations:

- Line
- Bar
- Pie
- Radar
- Heatmap
- Timeline

All charts must support:

- Zoom
- Tooltips
- Export as PNG
- Theme compatibility

## Color System

Primary: Blue

Success: Green

Warning: Amber

Danger: Red

Neutral: Gray

Use color only as an additional indicator, never the sole indicator.

## Typography

- Clear hierarchy
- Readable tables
- Consistent spacing
- Monospaced numbers where appropriate

## Icons

Use a single icon family across the application.

## Empty States

Every module should define:

- Empty state
- Loading state
- Error state
- No permission state

## Mobile

Responsive breakpoints:

- Mobile
- Tablet
- Desktop

## Accessibility

- WCAG AA target
- Keyboard navigation
- High contrast
- Screen reader labels

## Performance

- Lazy loading
- Virtualized tables
- Cached charts

## Future UX

- Dark mode
- Multi-language
- Drag & drop dashboards
- Dashboard customization
- Saved filters

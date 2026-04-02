# Landing Page

This page documents the landing experience served at `/` and how it is assembled.

## Purpose

The landing page introduces NetSense Campus, explains the value proposition, highlights the design thinking loop, and offers clear CTAs to the live heatmap.

## Primary Sections

- Hero: headline, value statement, stats, and CTA buttons.
- Project Overview: problem, solution, impact cards.
- Design Thinking Phases: empathize, define, ideate, prototype, test timeline.
- End-to-End Flow: scan to insight pipeline.
- Deep Dive Accordion: data model, aggregation, API, visualization, guardrails.
- CTA Footer: launch heatmap.

## Templates And Assets

- Template: `templates/heatmap/landing.html`
- Styles: `static/heatmap/css/style.css`
- Behavior: `static/heatmap/js/landing.js`
- Routes: `heatmap/views.py` -> `home_view` -> `/`

## Key CTAs

- `Open Live Heatmap` links to `/heatmap/`.
- `Design Thinking` jump link to `#design-thinking`.

## Notes

- The mini-map preview image uses a static asset in `static/heatmap/images/`.
- Scroll reveal animation is driven by the landing script and IntersectionObserver.

---
name: mobile-first-ux
description: Mobile-first UX policy for Job Finder. Use when writing or reviewing a spec, plan or code change that adds or changes any screen, component, form, table or email the user sees. Ensures phone layouts, states and one-tap actions per NFR-U requirements.
---

# Mobile-first UX check

The owner reviews packages and marks applications mostly on a phone. Design for a **360 px** wide screen first, then widen for desktop.

## For every screen or component in the change

- [ ] **Layout at 360 px** — no horizontal scrolling; tables become cards or stacked rows on narrow screens (NFR-U1).
- [ ] **Desktop at 1280 px** — uses the space; no stretched single column of text.
- [ ] **States** described: empty, loading, error, partial data (e.g. dossier with a source missing), long content.
- [ ] **Primary action reachable with one tap** — download the resume PDF, copy an answer, open the vacancy link, mark applied / skipped (NFR-U2).
- [ ] **Touch targets** at least 44×44 px; no hover-only actions.
- [ ] **Accessibility** — labels for inputs and icon buttons, colour contrast WCAG 2.2 AA, keyboard reachable (NFR-U4).
- [ ] **Speed** — the page is usable within 3 s on mobile 4G; heavy content (PDF preview, long dossiers) loads on demand (NFR-U3).
- [ ] **Language** — UI text in English; no jargon from the code (UC-NN, NFR IDs) visible to the user.

## Emails

- [ ] Readable on a phone mail client without zooming; one clear link per package to its page (UC-09).
- [ ] No resume text or personal data beyond what the summary needs.

## Output

Write into the spec's *UX* section: the screens, their states, the mobile and desktop layout in a sentence each, and the one-tap actions. Add acceptance criteria for the key mobile behaviour, for example:

> **ACn** — Given a prepared package, when the user opens it on a 360 px screen, then the "Download PDF" and "Copy" buttons are visible without horizontal scrolling.

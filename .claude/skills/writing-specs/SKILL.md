---
name: writing-specs
description: Use when writing or updating a spec.md (or an intent.md) for a Job Finder change in docs/changes/. Covers what to read first, how to fill the spec template, Given/When/Then acceptance criteria, and which policy skills to apply. Do not use for ADRs, plans or code.
---

# Writing a spec

A spec turns an accepted `intent.md` into requirements and design that a plan can be written from. It is reviewed by the owner before planning starts.

## 1. Read before writing

1. The issue and `docs/changes/<issue>-<slug>/intent.md`. No accepted intent → stop and ask for it.
2. `docs/vision.md` — scope and principles (§8 MVP scope, §9 principles).
3. `docs/requirements/use-cases.md` — the use cases this change touches (UC-NN).
4. `docs/requirements/nfr.md` — requirement IDs that apply.
5. `docs/adr/README.md` and every accepted ADR in the area of the change.

## 2. Fill the template

Copy `docs/templates/spec.md` to `docs/changes/<issue>-<slug>/spec.md` and fill every section. Delete a section only if it truly does not apply, and say so in one line.

- **Related ADRs** — list each relevant accepted ADR and how it constrains the design. If the design needs to contradict one, **stop**: write it under *Flagged concerns* and propose a new ADR instead of continuing.
- **Requirements** — functional requirements reference use cases; non-functional ones reference NFR IDs. Add a new numeric target only if no existing NFR covers it.
- **Acceptance criteria** — Given / When / Then, one observable result each, numbered AC1, AC2… Every functional requirement is covered by at least one criterion. Each criterion must be checkable by a test or an eval; avoid words like "fast", "nice", "properly".
- **Design** — only as much as the plan needs: components, data, interfaces, flows. Prefer the simplest design that meets the criteria.
- **Out of scope** — name what a reader might expect but is not included.

## 3. Apply the policy skills

Decide which policy skills apply, then **invoke each applicable one with the Skill tool** (do not just read its file) and write its result into the spec. Do not load skills that do not apply.

- `security-privacy` — **always**. Result → *Security, privacy and cost*.
- `cost-guard` — **always**. Result → *Security, privacy and cost*.
- `mobile-first-ux` — only if the change has a screen, component or email the user sees. Result → *UX*.
- `resume-rules` — only if the change generates, edits, reviews or shows resumes, added skills, answers or cover notes. Result → *Requirements* and *Acceptance criteria*.

## 4. Flag, don't hide

Conflicts with the vision, an ADR, an NFR target or another spec go to **Flagged concerns** with a proposed resolution and who decides (the owner). Do not silently pick a side.

## 5. Done when

- [ ] Every section filled or explicitly marked not applicable.
- [ ] Every requirement maps to a use case or an NFR ID, and to at least one acceptance criterion.
- [ ] All applicable policy skills applied and their results written in.
- [ ] No contradiction with accepted ADRs (or a flagged concern with a proposed ADR).
- [ ] Status set to *Draft* until the owner accepts it.

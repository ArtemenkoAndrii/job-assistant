---
name: resume-rules
description: Product rules for anything that generates, edits, reviews or displays tailored resumes, added skills, answers to application questions or cover notes in Job Finder. Use when writing specs, prompts, evals or code for tailoring, review, application packages or the reviewer agent.
---

# Resume rules (vision §9)

These rules protect the owner's reputation. Breaking them is a **blocker**, never a trade-off.

## Never invent experience

A tailored resume may **reorder, emphasise and rephrase** the base resume. It may **not** add roles, employers, projects, achievements, numbers, dates or years of experience that are not in the base resume.

## Added skills

A skill missing from the base resume may be added **only if all** hold:

1. It is **critical** for the vacancy — required or strongly preferred, not nice-to-have.
2. The owner can learn it at an **overview level within two weeks**.
3. It appears **only in the skills section**, never attributed to a past role, project or achievement.
4. It is listed separately as an **added skill** with *why needed* and *what to learn*, **highlighted** in the package and **rejectable** by the owner (UC-12).

## Answers and cover notes

- Built only from the base resume and the requirements file (UC-03). Missing data is shown as "add to the requirements file", never guessed.
- No claims about the employer that are not in the dossier with a source link.

## Reviewer agent

- Verdict judges **the resume only**: rule compliance and tailoring quality. Gaps between candidate and vacancy go to `fit_gaps`, not to `rework` (spike #3 finding).
- Max 2 rework rounds; then keep the best version with the reviewer's notes (UC-07).

## In specs, write

- A requirement for each rule the change touches.
- Acceptance criteria that an eval can check, for example:

> **ACn** — Given a base resume without Kubernetes and a vacancy that requires it, when the resume is tailored, then Kubernetes appears only in the skills section and in the added-skills list with a "what to learn" note.
>
> **ACm** — Given any vacancy, when the resume is tailored, then every employer, role, date and achievement in it exists in the base resume.

- Evals for these rules gate prompt and model changes (NFR-Q1, NFR-Q2, NFR-Q4).

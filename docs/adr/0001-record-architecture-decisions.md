# ADR-0001: Record architecture decisions

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Issue** | #8 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

Job Finder is built as an AI-native project: agents write most of the code, and specs and plans are produced in short sessions. Decisions that shape the whole system — hosting, storage, authentication, agent runtime, browser policy — must outlive any single session, be readable by people and agents, and be easy to find when a spec or a review needs them.

Several decisions were already taken during the feasibility spikes (#2–#4) and are recorded in the spike documents and issue comments. They need one home with a stable format.

## Decision drivers

- Agents and people must find the current decision in one place (maintainability, NFR-M1…M5).
- Specs (`spec.md`) and reviews must be able to check a change against accepted decisions.
- The process must be light enough for a single developer.

## Decision

We record architecture decisions as **ADRs in the repository**, one decision per file, in a lightweight format based on Michael Nygard's ADRs with an options section (MADR style).

### Location and naming

- Folder: `docs/adr/`.
- File name: `NNNN-short-title-in-kebab-case.md`, numbered sequentially from `0001`; numbers are never reused.
- `docs/adr/README.md` is the index: number, title, status, date.
- New ADRs start from [`template.md`](template.md).

### What gets an ADR

A decision gets an ADR when it is hard to reverse, affects several parts of the system, or constrains future specs: hosting, data storage, authentication, infrastructure as code, agent runtime and LLM provider, browser automation policy, email delivery, development environment, branching strategy. Choices local to one change belong in its `spec.md` or `plan.md`.

### Statuses

| Status | Meaning |
|---|---|
| **Proposed** | Under discussion in an open PR |
| **Accepted** | Merged into `main`; the decision is in force |
| **Rejected** | Considered and not taken; kept for the record |
| **Deprecated** | No longer relevant, nothing replaces it |
| **Superseded by ADR-NNNN** | Replaced by a newer ADR; the newer one says "Supersedes ADR-NNNN" |

### Lifecycle

1. The ADR issue (e.g. #15) is taken; a branch and an ADR file with status **Proposed** are created. Claude may draft the context, options and trade-offs.
2. The owner chooses the option; the PR is reviewed.
3. Before merge the status is set to **Accepted** (or **Rejected**) and the index is updated in the same PR. Merging the PR closes the issue. CI enforces it: `scripts/lint.sh` fails while any ADR is **Proposed**, so the required `ci` check blocks the merge (#59).
4. An accepted ADR is **not rewritten**. Typos and links may be fixed; a changed decision is a **new ADR** that supersedes the old one, and the old one's status is changed to *Superseded by ADR-NNNN* in the same PR.

### How ADRs connect to the rest of the SDLC

- `spec.md` has a **Related ADRs** section and must not contradict an accepted ADR. If it needs to, the spec work pauses and a new ADR is written first.
- `CLAUDE.md` carries a short ADR index (number, title, status) so agents load it into every session.
- `REVIEW.md` includes a check: *does the change contradict an accepted ADR?*
- Decisions already taken in spikes (OpenAI runtime models, agent with short tasks, manual submission, read-only browsing) are formalised in their ADR issues (#15–#21) and link back to the spike documents.

## Consequences

- Positive: one place for decisions, readable by agents; git history is the audit trail; reviews can check changes against decisions.
- Negative: a little overhead per decision; the index must be kept up to date (checked in review).
- Follow-ups: add the ADR index to `CLAUDE.md` and the ADR check to `REVIEW.md` when they are created (#10); add a **Related ADRs** section to the spec template (#10, #11).

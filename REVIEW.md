# Review guide

Used by human reviewers and by review agents for every pull request. Review the diff against its issue, `spec.md` and `plan.md` (if present) and the accepted ADRs.

## Passes

Run them in this order; report findings per pass.

1. **Correctness** — does the change do what the spec and acceptance criteria say? Logic errors, edge cases, error handling, data loss, concurrency (runs are sequential — NFR-R2).
2. **Security** — secrets in code, logs or config; missing authentication (NFR-S1); new network egress; tools given to agents (no form submission, no JavaScript, no account changes — NFR-B1, NFR-S6); untrusted page content treated as instructions.
3. **Privacy** — personal data stored, logged or sent to the LLM beyond what the step needs (NFR-P1, P5, P6); personal data or recordings in the public repo (NFR-P7).
4. **Decisions and scope** — contradicts an accepted ADR? Goes beyond the spec or the MVP scope in the vision? Changes a use case or NFR without updating the document?
5. **AI behaviour** — anything that generates resumes: no invented experience, added-skill rules (vision §9); prompt, model or agent changes are covered by evals (NFR-Q4).
6. **Cost** — new LLM calls, larger contexts or cloud resources; effect on NFR-C1 / NFR-C2.
7. **Tests and evidence** — tests for new behaviour; tests never hit real job boards (NFR-M5); `plan.md` proof is present and matches.

## Severity

| Severity | Meaning | Blocks merge |
|---|---|---|
| **Blocker** | Bug, security or privacy issue, ADR violation, invented experience possible, real job board in tests | Yes |
| **Major** | Missing tests for new behaviour, spec mismatch, cost or scope creep, missing doc update | Yes, unless the owner accepts it in the PR |
| **Nit** | Naming, style, small readability improvements | No |

Report at most **5 nits** per review; skip the rest.

## Out of scope for review

- `spikes/` — throwaway exploration code; review only for secrets and personal data.
- Generated files and lock files — review only that they belong to the change.
- Formatting that a formatter or linter enforces.

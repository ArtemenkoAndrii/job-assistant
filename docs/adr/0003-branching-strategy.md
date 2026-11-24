# ADR-0003: Branching strategy

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-24 |
| **Issue** | #12 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

One human owner and several AI agents (Claude Code in the dev container, cloud Claude sessions) change the repo. Agents write most of the changes; the owner reviews and merges every one. Work is tracked as GitHub issues, and each issue so far has gone through its own branch `<issue>-<slug>` and a PR with `Closes #N` (#35–#48). The first PRs were merged with merge commits, later ones with squash, because nothing fixed the method.

`main` has no protection: any token with write access, including one an agent uses, can push to it or rewrite it. The only guard is the "Never push to `main`" line in CLAUDE.md, and CLAUDE.md is advisory.

There is one deployable unit and one environment for now (the hosting decision is #15); there are no releases to maintain in parallel.

## Decision drivers

- Every change reviewed by the owner before it reaches `main` (vision: the owner stays in control; AI-native SDLC playbook: human gates).
- Agents must not be able to bypass review, even by mistake. Deterministic controls over instructions.
- Simple enough for one person; no process the project does not need.
- History that is easy to read and to revert per issue.
- CI (#13) and evals (#25) must be able to gate merges later without changing the flow.

## Options considered

### Option 1: Trunk-based, short-lived branches and PRs (GitHub flow)

`main` is always releasable. One branch per issue, merged through a PR within days.

- Good: what the project already does; one long-lived branch; fits continuous deployment from `main`.
- Good: each PR is small enough for the owner to review an agent's work.
- Bad: needs discipline to keep branches short; large features must be split into issues.

### Option 2: Git flow (`develop`, `release/*`, `hotfix/*`)

- Good: supports several released versions at once.
- Bad: there is one version and one environment; extra branches and merges add work and merge conflicts for no benefit.

### Option 3: Commit directly to `main`

- Good: fastest.
- Bad: no review gate for agent changes; incompatible with the owner-reviews-everything principle.

## Decision

**Option 1, trunk-based development with short-lived branches and PRs**, enforced on GitHub with a repository ruleset.

Flow:

1. Every change starts from an issue. Branch from the latest `main`, name `<issue>-<short-slug>` (e.g. `12-branching-strategy`).
2. Keep the branch short-lived: aim to merge within a few days. A change too big for that is split into more issues.
3. Open a PR with `Closes #N`. Draft while in progress; ready for review when the done checklist in CLAUDE.md is met.
4. The owner reviews and merges. Merge method: **squash only**; the squash commit is the PR title and number, so `main` has one commit per issue.
5. To bring a branch up to date with `main`, merge `main` into it; do not force-push a branch that is under review.
6. The branch is deleted after merge.
7. Parallel agent sessions use separate branches (or `git worktree`), never a shared one.

Enforcement — ruleset on the default branch, kept in the repo as [`.github/rulesets/main.json`](../../.github/rulesets/main.json). The owner applies it (Settings → Rules → Rulesets → Import a ruleset, or the API); agent sessions cannot change repository settings:

| Rule | Why |
|---|---|
| Pull request required, squash only | No direct pushes, one commit per issue |
| Required approvals: 0 | GitHub does not let the author approve their own PR, and PRs are opened with the owner's account; the owner's merge is the review |
| Conversations resolved before merge | Review comments cannot be skipped |
| Linear history | Follows from squash; no merge commits on `main` |
| Block force pushes and deletion | `main` cannot be rewritten or removed |
| No bypass actors | Applies to admins too; to change it, the ruleset itself is changed and recorded here |

Repository settings: squash merge only (merge commits and rebase merge disabled), squash commit title = PR title and the message = the branch's commit messages (keeps `Co-Authored-By` trailers), automatically delete head branches.

Out of scope: required status checks (added with CI in #13), required evals (#25), release tags and deployment (#15 and later).

## Consequences

- Positive: an agent cannot reach `main` without a PR, whatever token it holds and whatever its instructions say.
- Positive: `main` history is one squash commit per issue, easy to read and revert.
- Negative: hotfixes also need a PR; acceptable for one owner.
- Negative: the ruleset does not stop a token with admin rights from changing the ruleset. Agents must get tokens without admin rights (#13).
- Follow-ups:
  - #13 adds required status checks to this ruleset, a hook that blocks `git push` to `main` locally, and a minimal gh token for the dev container.
  - If a second human joins, raise required approvals to 1 and consider CODEOWNERS.

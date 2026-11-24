# Changes

Every change that adds or changes product behaviour goes through **intent → spec → plan → execution** ([AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)). Its artifacts live here, one folder per issue:

```
docs/changes/
  27-vacancy-search/
    intent.md   # what and why, in the originator's words — accepted by the owner
    spec.md     # requirements, acceptance criteria, design — accepted before planning
    plan.md     # files, steps, risks, proof — approved in plan mode before code
```

- Folder name: `<issue number>-<short-slug>`.
- Templates: [docs/templates](../templates/).
- Each artifact is committed and reviewed in the same PR as the code, or in an earlier PR when the gate needs a separate approval.
- If the implementation diverges from `plan.md`, the plan is updated in the same commit.

Not every change needs all three: a bug fix or a small refactor can go straight to a PR with a test; an architecture decision goes to [docs/adr](../adr/).

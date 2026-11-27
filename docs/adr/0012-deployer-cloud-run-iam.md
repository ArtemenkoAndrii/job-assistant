# ADR-0012: Deployer's Cloud Run IAM-policy right at project level

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-27 |
| **Issue** | #69 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |
| **Supersedes** | ADR-0009, the scope of `deployer`'s custom role only ("on `jobfinder-web`" and "on `jobfinder-worker`") |

## Context

[ADR-0009](0009-infrastructure-as-code.md) gives `deployer` a custom role with `run.services.setIamPolicy` and `run.jobs.setIamPolicy` **on `jobfinder-web` and `jobfinder-worker` only**, so the app layer can set who may invoke the service (the IAP agent) and start the job (`web`, `scheduler`).

#69 implemented "only" as a project-level grant with an IAM condition on `resource.type` and `resource.name`. The first deploy (2026-11-27) failed with `Permission 'run.services.setIamPolicy' denied` and `'run.jobs.setIamPolicy' denied`. Cloud Run does not support the resource name attribute in IAM conditions, and a condition on an attribute a service does not provide never grants access ([attribute reference](https://cloud.google.com/iam/docs/conditions-attribute-reference)). So the condition cannot express ADR-0009's scope.

The other way to scope it, a grant on the service and the job themselves, needs both to exist before the platform layer runs, but the app layer creates them.

## Decision drivers

- NFR-S4 and ADR-0009: least privilege for CI identities.
- A bootstrap that works in one pass and does not break if the service is recreated.
- No new tooling or ordering between the two Terraform layers.

## Options considered

### Option 1: unconditional grant at project level

- Good: one platform change; works on a fresh project and after the service or job is recreated.
- Bad: `deployer` can change the IAM policy of any Cloud Run service or job in the project.

### Option 2: grant on the two resources (resource-level IAM)

- Good: exactly ADR-0009's wording.
- Bad: the platform layer cannot grant on resources that do not exist yet: a fresh bootstrap becomes platform → deploy (fails) → platform → deploy; recreating the service drops the grant until the owner re-applies the platform layer.

## Decision

Option 1. The custom role `deployerRunIam` (`run.services.get/setIamPolicy`, `run.jobs.get/setIamPolicy`) is granted to `deployer` at project level, without a condition. Everything else in ADR-0009 stands.

Why the extra right is small:
- The project `job-finder` holds only `jobfinder-web` and `jobfinder-worker`.
- `deployer` already has `run.developer`, so it can already deploy any code to them.
- `deployer` runs only `deploy.yml` on `main` after review (WIF condition, ADR-0009).
- `scripts/check_infra.py` fails on `allUsers`/`allAuthenticatedUsers` in Terraform, the app layer sets `run.invoker` authoritatively (only the IAP agent on the service), and `drift.yml` reports any other change.

## Consequences

- Positive: the first deploy can finish; no ordering between layers.
- Negative: the scope is the project, not the two resources. If the project ever holds other Cloud Run resources, revisit this ADR.
- Follow-ups: none.

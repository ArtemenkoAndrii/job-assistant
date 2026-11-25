# ADR-0009: Infrastructure as code

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #16 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

ADR-0006, ADR-0007 and ADR-0008 decided the cloud resources. They all live in the GCP project `job-finder` (`us-central1`; the project ID gets a suffix, `job-finder-<suffix>`, because IDs are globally unique). The project is on the owner's personal billing account, which has no organization.

| Area | Resources |
|---|---|
| Compute | Cloud Run service `jobfinder-web` and job `jobfinder-worker`, one Cloud Scheduler job |
| Data | Firestore (TTL, indexes, backups, deny-all rules), a private bucket with a lifecycle rule, the Firebase link |
| Security | Secret Manager secrets; service accounts `web`, `worker`, `scheduler`, CI; IAP with the owner's access |
| Supporting | Artifact Registry, logging retention, a $5 budget |

What the NFRs require:
- every resource is in Terraform and drift is detectable (NFR-M3);
- CI deploys through Workload Identity Federation (WIF) with least privilege and no keys (NFR-S4);
- secrets live only in Secret Manager (NFR-S2).

Constraints:
- **ADR-0002:** the dev container has no cloud credentials, and agent sessions push branches. A branch must therefore not be able to read user data or secrets.
- **ADR-0008:** the repo and its Actions logs are public; the owner's email must not appear in either.

## Decision drivers

- Every change is reviewed in a PR before it is applied (ADR-0003).
- **No identity that a branch or a CI run can use may reach user data, secret values or the owner's email.**
- No keys anywhere.
- An honest boundary: whoever deploys the app's code can act as the app. That power is limited to reviewed code on `main`.
- Few manual steps, written down. One environment for a one-person MVP.

## Options considered

### Tool

**T1. Terraform** (Google provider 8.x, GA in October 2026).
- Good: the most common tool; agents know it best; NFR-M3 names it.
- Licence: BSL, which allows this use.

**T2. OpenTofu.**
- Good: fully open and language-compatible.
- Bad: a smaller ecosystem. Switching later is mostly a binary swap.

**T3. Pulumi.**
- Bad: less common for GCP; state lives in another service.

**T4. gcloud scripts.**
- Bad: no plan and no drift detection. Rejected.

### How the infrastructure is split

**S1. One Terraform root applied by CI.**
- Bad: CI's identity would need project-level IAM rights, secret and data administration. That identity could grant itself anything (verifier finding), and the state would hold the owner's email.

**S2. Two roots: a `platform` layer applied by the owner and an `app` layer applied by CI.**
- `platform` holds IAM, data, secrets and everything that rarely changes.
- `app` holds what changes with every release.
- CI never holds rights over IAM, data or secrets.

### Environments

**E1. One environment** (`prod`).
- Good: local development runs on fakes (ADR-0005, ADR-0007).
- Bad: a second project would double setup and drift for little gain at this stage.

## Decision

**T1 + S2 + E1.**

### Layers

| | `infra/platform` | `infra/app` |
|---|---|---|
| **Holds** | APIs; state bucket; WIF pool and provider; CI and runtime service accounts and **all** their roles; project-level IAM, including the owner's IAP access (granted at project level: with one IAP-protected resource it is equivalent to the service-level grant in ADR-0008, and it keeps the owner's email out of the app layer); Firestore database, TTL policy, backup schedule, security rules; files bucket with lifecycle and soft delete; Secret Manager secrets and their access bindings; Artifact Registry with cleanup policy; logging retention; budget; Firebase link | Cloud Run service (image digest, env, secret references, IAP on), Cloud Run job, Cloud Scheduler job, `run.invoker` for the IAP agent on the service, Firestore composite indexes |
| **Applied by** | the owner, from Cloud Shell, after the change is merged to `main` | CI (`deploy.yml`), on push to `main` |
| **State** | `gs://<state-bucket>/platform/`, readable only by the owner | `gs://<state-bucket>/app/`, readable by the CI accounts; holds no personal data |
| **Changes** | rarely: a new secret, a role, a retention rule | every release |

- Cloud Shell already has `gcloud` and Terraform and is signed in as the owner, so no key exists anywhere. After a platform apply, nothing stays in the Cloud Shell home: the state is remote, and the local `.terraform` and `terraform.tfstate*` from bootstrap are deleted after the migration.
- The owner's email is a variable of the **platform** layer only. It is entered in Cloud Shell and kept in the platform state; it never goes to GitHub.
- Versions: Terraform is pinned in `infra/.terraform-version`, the provider with `~> 8.0`, and both `.terraform.lock.hcl` files are committed. The image is referenced by digest.

### CI identities (WIF, no keys)

WIF pool `github`, provider `github-actions`:
- issuer `https://token.actions.githubusercontent.com`;
- attribute condition on **numeric IDs**: `assertion.repository_owner_id == '19709306' && assertion.repository_id == '1464306064'`;
- mapped attributes: `event_name`, `ref`, `workflow_ref`.

| Service account | Principal that may use it | Roles (all in `job-finder`) |
|---|---|---|
| `app-plan` | any workflow run of this repo (pull requests from its branches) | `run.viewer`, `cloudscheduler.viewer`, `datastore.indexViewer`, `iam.serviceAccountViewer`; `storage.objectViewer` on the `app/` prefix of the state bucket (IAM condition) and `storage.objects.list` on the bucket (custom role; lists names only). It plans with `-lock=false`, so it can neither write nor lock the state. **No** data, secret, IAM-admin or platform-state access |
| `deployer` | only `workflow_ref == 'ArtemenkoAndrii/job-assistant/.github/workflows/deploy.yml@refs/heads/main'` **and** `event_name == 'push'` | `run.developer`; `iam.serviceAccountUser` on `web`, `worker` and `scheduler` only; `cloudscheduler.admin`; `datastore.indexAdmin`; `artifactregistry.writer` on the image repository; `storage.objectUser` on `app/` state; a custom role with `run.services.setIamPolicy` on `jobfinder-web` (invoker for the IAP agent) and `run.jobs.setIamPolicy` on `jobfinder-worker` (who may start it: `web` and `scheduler`, ADR-0006). **No** project IAM, data, secret-value, bucket-admin or billing rights |

- **Forks:** pull requests from forks get no OIDC token, so they cannot use either account.
- **Other triggers:** binding `deployer` to the workflow file and the `push` event keeps `pull_request_target`, `workflow_run`, `issue_comment` and `workflow_dispatch` runs on `main` away from it. `scripts/lint.sh` will also fail on any `pull_request_target` workflow (added in #22).

**The real boundary, stated plainly.** `deployer` deploys images that run as `web` and `worker`, and those accounts can read data and secrets. Whoever controls the deployed code can therefore act as the app. That power is limited to code that reached `main` through a reviewed PR (ADR-0003). `deployer` itself cannot grant roles, read data or read secret values. A branch or a pull request (`app-plan`) can reach neither.

### Workflows

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | every PR | adds `terraform fmt -check` and `terraform validate` (no backend) for both layers |
| `app-plan.yml` | PRs that change `infra/app/**` or `apps/**` | `terraform plan` of the app layer as `app-plan`; the output holds no personal data |
| `deploy.yml` | push to `main` that changes `infra/app/**` or `apps/**` | build and push the image, `terraform apply` of the app layer as `deployer` with the new digest, then a smoke check |
| `drift.yml` | weekly | plan of the **app** layer as `app-plan`; fails on any difference |

The platform layer is not planned by CI: that would need read access to IAM, data and billing. The owner runs `terraform plan` of the platform layer in Cloud Shell once a month and after every platform change. This is a recorded exception to NFR-M3's "from CI" (NFR-M3 updated in this PR).

The GitHub Environment `production` (deployments only from `main`) holds only non-secret identifiers as variables: project ID and number, WIF provider, service account emails. No secret is needed in GitHub.

### Secrets

Terraform (platform layer) creates the Secret Manager **secrets and their access bindings**. The **values** are added once by the owner with `gcloud secrets versions add`, so they never pass through the repo, CI or any state:
- A-1 client id and secret;
- the OpenAI key;
- the email key (#21);
- the owner email for the app's check (ADR-0008).

### One-time manual steps (owner)

These become a runbook, `docs/runbooks/bootstrap.md`, in #22:
1. Create the project `job-finder-<suffix>` and link the billing account.
2. In the Console, add Firebase to the project. This accepts the Firebase terms; Terraform then manages the rest.
3. In Cloud Shell, clone the repo and apply `infra/platform`. It starts with local state, then the state is migrated to the bucket and the local state files are deleted.
4. In the Console, create the IAP OAuth client (External, In production; ADR-0008). Attach it with `gcloud iap settings set`. The client secret stays with IAP, not in Terraform. This must happen before the first `deploy.yml` run enables IAP.
5. Add the secret values (above).
6. Set the variables of the GitHub Environment `production`.

After that, app changes go through PRs and `deploy.yml`. Platform changes go through PRs and an owner apply in Cloud Shell.

Out of scope:
- the code of both layers and the first deployment (#22);
- monitoring beyond the budget (#33);
- a second environment (revisit when the product gets other users).

## Consequences

- Positive: every resource is in Terraform and reviewed in a PR. App drift is checked weekly by CI, platform drift monthly by the owner.
- Positive: no key exists. No branch or pull request can reach data, secret values or the owner's email. CI cannot change IAM.
- Positive: the deployment boundary is explicit: reviewed code on `main`.
- Negative: two layers and a few manual steps. Platform changes need the owner in Cloud Shell; they are rare.
- Negative: NFR-M3 is relaxed: the platform layer is applied and drift-checked by the owner, not CI.
- Negative: one environment, so a bad deploy hits the only environment. Deploys are small, reviewed and smoke-checked, and can be rolled back to the previous digest.
- Follow-ups:
  - **#22:** `infra/platform`, `infra/app`, the workflows, the `pull_request_target` lint rule, a check that fails if `allUsers` gets any role on the service, the runbook, the first deploy; confirm the GCS backend works with `app-plan`'s read-only roles.
  - **Tooling:** Terraform in the dev container; `terraform fmt` in `scripts/lint.sh`; `validate` in CI (needs the registry).
  - **ADR-0006 and ADR-0007** listed a `deployer` with "no data access". This ADR makes that precise: no data or IAM rights of its own, but it deploys code that runs with the app's access.
  - **Docs on acceptance:** NFR-M3 wording; architecture Q3; CLAUDE.md index.

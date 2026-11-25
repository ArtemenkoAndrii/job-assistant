# ADR-0009: Infrastructure as code

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #16 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

ADR-0006, ADR-0007 and ADR-0008 decided the cloud resources. All of them are in the GCP project `job-finder` (`us-central1`), on the owner's billing account. That account is personal, with no organization.

| Area | Resources |
|---|---|
| Compute | Cloud Run service `jobfinder-web`, Cloud Run job `jobfinder-worker`, one Cloud Scheduler job |
| Data | Firestore with TTL, indexes, backups and deny-all rules; a private bucket with a lifecycle rule; Firebase link |
| Security | Secret Manager secrets; service accounts `web`, `worker`, `scheduler`, `deployer`; IAP with the owner's access |
| Supporting | Artifact Registry; Logging retention; a $5 budget |

What the NFRs require:
- **NFR-M3:** 100% of cloud resources are created by Terraform from CI, and `terraform plan` shows no drift.
- **NFR-S4:** CI deploys through Workload Identity Federation (WIF), with no long-lived keys and least privilege.
- **NFR-S2:** secrets live only in Secret Manager.

Constraints that shape the setup:
- The dev container has no cloud credentials (ADR-0002).
- The repo and its Actions logs are public.
- The owner's email must not appear in either (ADR-0008).

Some things cannot be created by CI from nothing:
- the project, its billing link and the budget (they need billing-account rights);
- the WIF pool that CI itself uses to sign in;
- the IAP OAuth client in a project without an organization (a one-time Console step).

## Decision drivers

- Everything reviewable in a PR and applied by CI after the owner's merge (ADR-0003).
- No service account keys anywhere; CI identities as narrow as possible.
- No secret values or personal data in the repo, CI logs or variables that print.
- Few manual steps, all written down; one environment for a one-person MVP.
- Detectable drift.

## Options considered

### Tool

**T1. Terraform** (Google provider; 8.0 GA in October 2026) vs **T2. OpenTofu** (open-source fork, same language) vs **T3. Pulumi** (Python) vs **T4. gcloud scripts**.
- **T1:** the most common tool; agents and examples know it best; the issue and NFR-M3 name it. Its licence (BSL) allows this use.
- **T2:** compatible and fully open, but a smaller ecosystem; switching later is mostly a binary change.
- **T3:** the same language as the app, but less common for GCP, and the state lives in another service.
- **T4:** no state, no plan, no drift detection. Rejected.

### Environments

**E1. One environment (`prod`)** vs **E2. `dev` + `prod` projects.**
- **E1:** for one user, local development already runs on fakes (ADR-0005, ADR-0007), and the free tiers count per billing account.
- **E2:** a second project doubles the setup and the drift surface for little gain at this stage.

### Who applies

**A1. CI applies on merge to `main`** vs **A2. the owner applies from their machine.**
- **A1:** NFR-M3 asks for CI; the PR shows the plan before merge.
- **A2:** keeps credentials on a laptop and skips review.

## Decision

**T1 + E1 + A1, with a small bootstrap applied once by the owner.**

### Layout

```
infra/
  bootstrap/    # applied once by the owner from Cloud Shell; local state, then migrated to the bucket
    project services (APIs), state bucket, WIF pool + provider, CI service accounts,
    budget $5 with alerts, Artifact Registry
  main/         # applied by CI
    cloud_run.tf     web service (IAP), worker job, scheduler job
    data.tf          Firestore (TTL, indexes, backup schedule, rules), bucket (lifecycle, soft delete), Firebase link
    secrets.tf       secret containers and access bindings (no values)
    iam.tf           runtime service accounts and their roles, IAP access for the owner
    variables.tf     image digest, owner email (sensitive), project number
```

The Terraform version is pinned in `infra/.terraform-version`, the provider with `~> 8.0`, and `.terraform.lock.hcl` is committed. The image is pinned by digest, not by tag.

### State

One GCS bucket `job-finder-tfstate-<suffix>` in `job-finder`:
- private, uniform access, object versioning on;
- readable and writable only by the CI service accounts and the owner.

State can hold sensitive values (the owner email), which is why the bucket is private. No secret values go into Terraform at all (see below).

### CI access (WIF, no keys)

WIF pool `github` with provider `github-actions`:
- **Issuer:** `https://token.actions.githubusercontent.com`.
- **Attribute condition** on numeric IDs, not names, to rule out look-alike repos: `assertion.repository_owner_id == '19709306' && assertion.repository_id == '1464306064'`.

Two service accounts, each bound to a narrower principal set:

| Service account | Who can use it | Can do |
|---|---|---|
| `tf-plan` | workflows of this repo on any event (pull requests from branches of this repo) | read-only roles to run `terraform plan`; read the state |
| `deployer` | only workflows on `refs/heads/main` (mapped `attribute.ref`) | apply `infra/main`, push images, deploy Cloud Run, set IAM on the project's resources; **no** access to data (Firestore, bucket objects) or to secret values; **no** billing or project-level owner rights |

Pull requests from forks get no OIDC token from GitHub, so they cannot plan. The repo also requires a PR from a branch of this repo before anything reaches `main` (ADR-0003).

### Workflows

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` (existing) | every PR | adds `terraform fmt -check` and `terraform validate` for `infra/` |
| `infra-plan.yml` | PRs that change `infra/**` | `terraform plan` as `tf-plan`; the summary goes to the job log, with sensitive values masked |
| `deploy.yml` | push to `main` that changes `apps/**` or `infra/**` | build and push the image, then `terraform apply` as `deployer` with the new image digest; then the smoke check |
| `drift.yml` | weekly | `terraform plan -detailed-exitcode` as `tf-plan`; fails if anything differs (NFR-M3) |

GitHub Environment `production`:
- deployments allowed only from `main`;
- holds the non-secret IDs as variables (project id and number, pool provider, service account emails);
- holds the owner email as an environment **secret** (`TF_VAR_owner_email`), which Terraform marks `sensitive`.

### Secrets

Terraform creates the Secret Manager **secrets and their access bindings**. The **values** are added once by the owner in the Console or with `gcloud secrets versions add`, so they never pass through the repo, CI or Terraform state:
- A-1 client id and secret;
- the OpenAI key;
- the email key (#21);
- the owner email for the app (ADR-0008).

### One-time manual steps (owner)

These go into a runbook, `docs/runbooks/bootstrap.md`, written in #22:
1. Create the project `job-finder-<suffix>` and link the billing account.
2. In Cloud Shell, clone the repo and run `terraform apply` in `infra/bootstrap`. Cloud Shell already has `gcloud` and Terraform and is signed in as the owner, so no keys are needed anywhere. Then migrate the bootstrap state to the bucket.
3. In the Console, create the IAP OAuth client (External, In production; ADR-0008).
4. Add the secret values (above).
5. In the GitHub Environment `production`, set the variables and the owner-email secret.

Everything after that goes through PRs and `deploy.yml`.

Out of scope:
- the application code and the first deployment (#22);
- monitoring alerts beyond the budget (#33);
- a second environment (revisit when the product gets other users).

## Consequences

- Positive: every resource is in code, reviewed in a PR and applied by CI; drift is caught weekly.
- Positive: no keys exist. CI identities are tied to this repo by numeric ID; only `main` can deploy; `deployer` cannot read user data or secret values.
- Positive: secret values and the owner email stay out of the repo and the public logs.
- Negative: a few manual steps that code cannot do (project, billing link, bootstrap, OAuth client, secret values); they are written down, and they are rare.
- Negative: one environment, so a bad deploy affects the only environment. Accepted for a single-user MVP: deploys are small, reviewed, smoke-checked, and can be rolled back to the previous image digest.
- Negative: plans run in public logs, so values must be marked `sensitive`, and the plan summary must not print resource bodies that could contain personal data.
- Follow-ups:
  - #22: write `infra/bootstrap`, `infra/main` and the workflows; the runbook; the first deploy.
  - Terraform and tflint in the dev container (offline `fmt` in `scripts/lint.sh`; `validate` in CI, because it needs the provider registry).
  - Update [architecture](../architecture.md) Q3 on acceptance.

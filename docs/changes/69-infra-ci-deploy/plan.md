# Plan: Infrastructure and CI deploy (skeleton 1/3)

| | |
|---|---|
| **Issue** | #69 |
| **Spec** | [spec.md](spec.md) |
| **Status** | Approved |
| **Date** | 2026-11-26 |

## Context

Nothing deploys yet. The ADRs (0005–0009) are unproven until a build reaches Cloud Run from `main` without keys. Existing pieces reused: `/healthz` in `apps/jobfinder/src/jobfinder/web/app.py`, worker stub `jobfinder/worker/__main__.py` (exits 0), `apps/jobfinder/Dockerfile` (uvicorn, `$PORT`), `ci.yml` (job `ci`, SHA-pinned actions, gitleaks install via `.devcontainer/install-gitleaks.sh`), `scripts/lint.sh` `run` helper, `.gitignore` already ignores `*.tfstate*`, `.terraform/`, `*.tfvars`. No application code changes are needed.

## Files that change

| File | Change |
|---|---|
| `docs/changes/69-infra-ci-deploy/plan.md` | new, this plan (first commit) |
| `.devcontainer/install-terraform.sh` | new: installs the Terraform version from `infra/.terraform-version`, verifies the SHA256SUMS file (pattern of `install-gitleaks.sh`); used by the Dockerfile and CI |
| `.devcontainer/Dockerfile` | install Terraform at build time (pinned) |
| `.devcontainer/allowed-domains.txt` | + `registry.terraform.io`, `releases.hashicorp.com` with a comment why (R8) |
| `infra/.terraform-version` | new, pinned version |
| `infra/platform/*.tf` | new: `versions.tf`, `variables.tf`, `apis.tf`, `state.tf`, `wif.tf`, `iam.tf`, `firestore.tf`, `storage.tf`, `secrets.tf`, `registry.tf`, `logging.tf`, `budget.tf`, `firebase.tf`, `outputs.tf`, `terraform.tfvars.example`, `.terraform.lock.hcl` (generated for `linux_amd64` and `linux_arm64`, with `terraform providers lock`) |
| `infra/app/*.tf` | new: `versions.tf` (empty GCS backend, bucket via `-backend-config`), `variables.tf`, `cloud_run_web.tf` (IAP on, invoker for IAP agent, startup probe), `cloud_run_worker.tf`, `scheduler.tf`, `outputs.tf`, `.terraform.lock.hcl` (both platforms) |
| `.github/actions/bootstrap-guard/action.yml` | new: composite action, the shared guard step of `deploy.yml`, `app-plan.yml` and `drift.yml` |
| `.github/workflows/ci.yml` | add Terraform install, `terraform fmt -check -recursive infra`, `init -backend=false` + `validate` per layer |
| `.github/workflows/app-plan.yml` | new: PR, `app-plan` via WIF, `plan -lock=false` |
| `.github/workflows/deploy.yml` | new: push to `main`, bootstrap guard, build/push, apply with digest, wait Ready |
| `.github/workflows/drift.yml` | new: weekly, `app-plan`, `-detailed-exitcode` |
| `scripts/check_infra.py` | new: fails on `pull_request_target` in workflows and on `allUsers`/`allAuthenticatedUsers` in `*.tf` |
| `scripts/lint.sh` | + `check_infra.py` and `terraform fmt -check` (skipped locally if terraform missing, required in CI, same pattern as uv/gitleaks) |
| `scripts/test.sh` | + `unittest discover -s tests/scripts` |
| `tests/scripts/test_check_infra.py` | new: AC10 cases (bad and good fixtures built in a temp dir) |
| `docs/runbooks/bootstrap.md` | new (R5) |
| `CLAUDE.md`, `docs/dev-environment.md`, `docs/architecture.md` | table row for `infra/` and `docs/runbooks/`, Terraform in the dev container, deployment section points to the runbook; ADR index unchanged |

Not touched: `apps/jobfinder/**`, Dockerfile of the app.

## Steps
Each step is a commit; run `scripts/build.sh`, `scripts/lint.sh`, `scripts/test.sh` before each (with `UV_CACHE_DIR` set if the sandbox cache is read-only).

1. **Save plan.md** (this plan). Commit.
2. **Tooling:** `install-terraform.sh`, Dockerfile, allowed domains, `infra/.terraform-version`; `check_infra.py` + tests + lint/test wiring (test first: failing fixture, then the check). Commit.
3. **`infra/platform`**, in this order, each file small:
   - `variables.tf`: `project_id`, `region` (default `us-central1`), `billing_account` (sensitive), `owner_email` (sensitive), `github_repository_id` and `github_owner_id` (defaults are the numeric IDs already public in ADR-0009), `state_bucket`, `files_bucket`, `budget_amount` (5). Real values go in a gitignored `terraform.tfvars` in Cloud Shell; `terraform.tfvars.example` has placeholders only.
   - `apis.tf` (cloudresourcemanager, serviceusage, firebaserules, run, cloudscheduler, firestore, secretmanager, artifactregistry, iam, iamcredentials, sts, iap, firebase, billingbudgets, storage, logging); `state.tf` (versioned, private bucket, `prevent_destroy`); `wif.tf` (pool `github`, provider `github-actions`, attribute condition on numeric IDs, mapped `event_name`, `ref`, `workflow_ref`).
   - `iam.tf`: service accounts `web`, `worker`, `scheduler`, `app-plan`, `deployer`; every role of ADR-0006/0009 (custom roles for `storage.objects.list` and for the two `setIamPolicy` permissions); principal bindings: `app-plan` ← any run of the repo; `deployer` ← `workflow_ref` of `deploy.yml@refs/heads/main` and `event_name == 'push'`; owner `iap.httpsResourceAccessor` at project level; IAM conditions for state-bucket prefixes.
   - `firestore.tf` (Native, `us-central1`, TTL on `expire_at` for the TTL collections, daily backup schedule with 7-day retention, rules file denying all client access); `storage.tf` (uniform access, public access prevention, soft delete 7 days, lifecycle `packages/pending/` age 90); `secrets.tf` (5 secrets as containers + accessor bindings per ADR-0006 identities, **no `google_secret_manager_secret_version`**); `registry.tf` (cleanup keep last 3); `logging.tf` (30-day `_Default` retention); `budget.tf` ($5, thresholds 0.5/0.9/1.0, email to the owner); `firebase.tf`; `outputs.tf` (non-secret identifiers the owner pastes into the GitHub Environment). The project number comes from `data "google_project"`, not a variable. The IAP service agent is created explicitly with `google_project_service_identity` (provider `google-beta`), so it exists before the app layer grants it `run.invoker`. `versions.tf` has the `gcs` backend block with no bucket; the bootstrap applies with `terraform init -backend=false` (local state), then `terraform init -migrate-state -backend-config=bucket=<state-bucket>` moves it (runbook). `app-plan` and `deployer` get no role on the `platform/` prefix (it holds the owner email and the billing account); the IAM conditions are on `app/` only (AC13 checks it).
   - Validate with `terraform init -backend=false && terraform validate`, `fmt`. Commit.
4. **`infra/app`**: web service `jobfinder-web` (`iap_enabled`, `ingress` all, min 0/max 2, 1 vCPU/512 MiB, `startup_cpu_boost`, startup probe `GET /healthz`, env `PORT` default, runs as `web`), `google_cloud_run_v2_service_iam_member` `run.invoker` for the IAP service agent only; job `jobfinder-worker` (1 task, parallelism 1, timeout `7200s`, `max_retries = 0`, 1 vCPU/1 GiB, `python -m jobfinder.worker`, runs as `worker`); Scheduler `30 * * * *` calling the job `:run` as `scheduler`; invoker bindings on the job for `web` and `scheduler`; the IAP agent's address is built from the project number, which the app layer takes from the Environment variable (`app-plan` has no `resourcemanager.projects.get`); image variable is a full digest reference (validated by a `validation` block, so a tag is rejected). No composite indexes (comment says why). Commit.
5. **Workflows** (actions pinned by commit SHA resolved with `gh api`, permissions minimal, `persist-credentials: false`):
   - `bootstrap-guard` composite action (used first in `deploy.yml`, `app-plan.yml`, `drift.yml`): all Environment variables empty → output `ready=false` and `::notice::bootstrap not done, see runbook`, exit 0; all set → `ready=true`; some set and some empty → fail with the names of the empty ones. Later steps run only `if: steps.guard.outputs.ready == 'true'`.
   - `ci.yml`: no cloud access.
   - `app-plan.yml`: `permissions: id-token: write, contents: read, pull-requests: read`; `google-github-actions/auth` with the Environment variables; `terraform init -backend-config=bucket=...`, `plan -lock=false -input=false -var image=<deployed digest>`. The digest is read with `gcloud run services describe jobfinder-web` (resolved to `repo@sha256:…`), so the plan shows no image diff and passes validation; if the service does not exist yet, a fixed all-zero digest is used. Skipped on fork PRs by design (no token).
   - `deploy.yml`: `on: push` to `main`, paths `infra/app/**`, `apps/**`; `environment: production`; `concurrency: { group: deploy, cancel-in-progress: false }`; step 1 is the guard; later steps: auth, `docker build/push` to Artifact Registry, resolve digest (`docker inspect` RepoDigests), `terraform apply -auto-approve -var image=<digest>`, `gcloud run services describe` loop until `Ready=True` on the latest revision (timeout 5 min). No `/healthz` call.
   - `drift.yml`: `schedule: weekly` and `workflow_dispatch` (AC4 needs a manual run), guard step, same deployed-digest `-var image=` as `app-plan.yml`, plan with `-detailed-exitcode`, exit 2 → fail.
   Commit.
6. **Runbook + docs** (R5): numbered owner steps, each with the exact command; ordering note that the IAP client exists before the re-run; last step "Re-run latest `deploy.yml`"; monthly platform plan; rollback by digest; the GitHub Environment `production` is limited to deployment branches = `main` only; the custom OAuth client is attached with `gcloud iap settings set` at project level (the client secret never goes to state or the repo); a "what each secret value is and when to add it" table. Update the docs listed above; check Markdown links with `scripts/lint.sh`. Commit.
7. **Verifier and PR:** run the `verifier` subagent with `#69`. It checks the acceptance criteria that can be proved before merge and lists the post-bootstrap ones (AC3, AC4, AC5, AC8, AC9, AC11, AC12, AC13, AC15 to AC19) as pending; quote its verdict in the PR. The agent's token has no Workflows permission, so the agent only commits; **the owner pushes the branch from the host** and opens the PR, which says `Refs #69` (not `Closes`). The agent does not ask for wider token rights. The owner reviews and squash-merges.
8. **After merge, owner bootstraps** (I assist, cannot touch GCP: the sandbox has no credentials). Merge triggers `deploy.yml` → green "bootstrap not done" (AC17). Owner follows the runbook; re-run (AC18). Measurements (cold start, image size, AC15/19) and the other post-bootstrap evidence are pasted into Proof in a follow-up PR with `Closes #69`; the issue closes when they are recorded.

## Risks

| Risk | Mitigation |
|---|---|
| Terraform cannot be run here (not installed; sandbox firewall) so syntax and provider-argument mistakes surface late | Install Terraform in the container image (R8) and in CI; `validate` in `ci.yml` is the first gate; keep the code small and use only documented v8.x arguments, checked against the provider docs while writing |
| `iap_enabled` on `google_cloud_run_v2_service` or the IAP agent's address differs from ADR-0008 assumptions | Check provider docs in step 4; if the argument is beta-only or absent, stop and report (it would contradict ADR-0008) rather than work around |
| Provider/GitHub-action versions chosen from memory | Resolve exact versions and SHAs with `gh api` and the registry; lock files committed |
| `deployer` rights insufficient (e.g. `terraform apply` needs `run.services.get/update`, `iam.serviceAccounts.actAs`, Artifact Registry read of the image) | Roles come straight from ADR-0009; first live apply by the owner may need a platform-layer fix, handled as a normal platform change; recorded in the Divergence log |
| App-layer apply by `deployer` also needs read access to the state of platform outputs | Not used: the app layer takes identifiers as variables, never reads the platform state |
| `app-plan` with `-lock=false` and read-only roles cannot refresh some resources | Confirm on the first PR run (ADR-0009 follow-up); adjust the viewer roles in the platform layer if needed |
| Cold start above 10 s on 512 MiB | Measure first; raise memory/CPU or trim the image (NFR-A1) and record the change |
| The `google_billing_budget` resource may need `user_project_override = true` and `billing_project` on the provider when applied with the owner's user credentials in Cloud Shell | Set both in the platform provider block; confirm on the first apply, record in the Divergence log |
| The app layer cannot derive the project number with `data "google_project"` (`app-plan` lacks `resourcemanager.projects.get`) | Keep it an Environment variable in the app layer; adding the permission to both CI roles would be a platform change and an ADR-0009 deviation |
| Leaking identifiers (project number, billing account, owner email) into the public repo | `terraform.tfvars` is gitignored; examples hold placeholders; gitleaks and review; project number lives only in Environment variables |

## Proof

Commands pasted into the PR: `scripts/build.sh`, `scripts/lint.sh`, `scripts/test.sh`.

| Acceptance criterion | Evidence |
|---|---|
| AC1 | `ci.yml` run: fmt and validate steps green with no credentials |
| AC2, AC6 | `gcloud iam workload-identity-pools providers describe` and `gcloud iam service-accounts get-iam-policy deployer` output pasted in the PR (config inspection) |
| AC3 | `app-plan.yml` run on this PR after bootstrap, or on the first infra PR that follows |
| AC4 | first scheduled or manually triggered `drift.yml` green; then a manual console edit makes it red, reverted |
| AC5, AC18 | `deploy.yml` run after the re-run: image digest in the log, apply output, Ready revision |
| AC7 | `scripts/lint.sh` gitleaks "no leaks found"; screenshot or `gh api` list of Environment variables (names only) |
| AC8 | `curl -sI https://<service-url>/healthz` → IAP redirect/401, plus `gcloud run services get-iam-policy` shows only the IAP agent |
| AC9 | owner opens `/healthz` through IAP in a browser: JSON status+version |
| AC10 | `tests/scripts/test_check_infra.py` |
| AC11 | owner's `terraform plan` in Cloud Shell "No changes" + console check list |
| AC12 | `gcloud secrets versions list` per secret: empty |
| AC13 | `gcloud projects get-iam-policy` filtered by the two accounts, plus the bucket IAM policy: neither account has any role on the `platform/` prefix |
| AC14 | runbook order reviewed in the PR |
| AC15 | Cloud Run `container/startup_latencies` and request log latency after 15 min idle; **value recorded here**: _to fill_; image size from `docker images` / Artifact Registry: _to fill_ |
| AC16 | `gcloud run jobs execute jobfinder-worker --wait`, exit 0 |
| AC17 | the `deploy.yml` run triggered by the merge: green with "bootstrap not done" |
| AC19 | Cloud Run job execution list after 2 h: executions at :30, all succeeded |
| AC20 | `terraform version` and `init -backend=false && validate` output from the rebuilt dev container |

## Divergence log

**Pre-implementation review (2026-11-26)**, by the owner; Status stays Approved:

- The main PR says `Refs #69`; a follow-up PR with the post-bootstrap Proof says `Closes #69`; the verifier lists the post-bootstrap ACs as pending.
- `app-plan.yml` and `drift.yml` pass the deployed digest as `-var image=`.
- Shared bootstrap guard: all variables empty → green notice; partly set → fail.
- Platform state: bootstrap with `-backend=false`, then `-migrate-state`; `app-plan` and `deployer` cannot read the `platform/` prefix.
- IAP: runbook binds the OAuth client at project level; the IAP service agent is created explicitly in the platform layer.
- The owner pushes the branch from the host; the agent token is not widened.
- Added APIs `cloudresourcemanager`, `serviceusage`, `firebaserules`; budget provider risk added.
- `deploy.yml` concurrency group; `drift.yml` keeps `workflow_dispatch`; runbook limits the Environment to `main`.
- Project number from `data "google_project"` in the platform layer (the app layer keeps the variable, see Risks); lock files for `linux_amd64` and `linux_arm64`.
- The ADR-0008 header note was dropped from the file list (reverted on the owner's request).

**Implementation**

- Step 2: `scripts/check_infra.py` also checks the Terraform pin: the Dockerfile `TERRAFORM_VERSION` must equal `infra/.terraform-version`. Terraform is pinned to 1.17.2 (newest stable, by numeric sort).
- Step 2, owner review: `install-terraform.sh` verifies the zip against SHA256 values pinned in the repo, `infra/.terraform-sha256` (`sha256sum` format, `linux_amd64` and `linux_arm64`), not against a checksum file from the release host. The Dockerfile build context is `.devcontainer/`, so it mirrors the hashes as build ARGs and `check_infra.py` fails if they differ from the file. The hashes first were placeholders (the sandbox could not reach `releases.hashicorp.com`, proxy 502) and the dev container build failed at the checksum step; the owner supplied the official values for 1.17.2, now in `infra/.terraform-sha256` and the Dockerfile ARGs. `install-terraform.sh` fails with a message that names the file, the zip and the likely cause when a hash is missing, malformed or still a placeholder, and when the architecture is unsupported; `check_infra.py` warns locally and fails in CI on a placeholder.
- Step 2, owner review: no separate Claude Code sandbox allowlist exists in the repo (`.claude/settings.json` has no `sandbox.network`; `.devcontainer/claude-settings.json` only enables the sandbox). The sandbox allows network per command with approval (`allowed_domains`), so `registry.terraform.io` and `releases.hashicorp.com` need no settings change; the dev container firewall allowlist (`allowed-domains.txt`) is the only guardrail change, to be explained in the PR.
- Step 3: WIF mapping adds `attribute.deploy_trigger` (`event_name:workflow_ref`) and `attribute.repository_id`: a principal binding matches one attribute, so `deployer`'s two conditions (`deploy.yml` on `main`, `push` event) are combined into one value. `event_name`, `ref` and `workflow_ref` stay mapped as in ADR-0009.
- Step 3: `app-plan` has no datastore index viewer role (ADR-0009 lists one; as far as known no such role exists, and the app layer has no composite index yet).
- Step 3: `deployer`'s custom role for `setIamPolicy` also carries `getIamPolicy`, and is bound at project level with IAM conditions on the resource type and name suffix (`/services/jobfinder-web`, `/jobs/jobfinder-worker`), because the resources do not exist when the platform layer is applied. The condition syntax is verified only by the first real apply.
- Step 3: `terraform validate` cannot run inside the Claude Code sandbox (provider plugins need a Unix socket); it ran after the owner excluded `terraform` from the sandbox. `init` needs `registry.terraform.io` and `releases.hashicorp.com`, and the sandbox reported `checkpoint-api.hashicorp.com` (version check) as denied, harmless.
- Step 4: `iap_enabled` exists on `google_cloud_run_v2_service` in provider 8.12.0 (`validate` accepts it), so the IAP risk in Risks is closed. The IAP agent and the job invokers use authoritative `*_iam_binding` resources, so any other member (including `allUsers`) shows as drift.
- Step 4: the app layer builds service account addresses from `project_id` (`web@<project>.iam.gserviceaccount.com`, and so on) and never reads the platform state. Variables: `project_id`, `project_number`, `region`, `image` (a `validation` block rejects anything but a digest reference). The startup probe allows 60 s (period 2 s, 30 failures) before the revision is marked failed.
- Step 4: a plain `terraform …` command runs outside the sandbox (owner's exclusion); a compound command (`a; b`, `cd … && terraform …`) does not and fails on the plugin socket.
- Step 5, **needs the owner's decision**: the non-secret identifiers (`GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_WIF_PROVIDER`, `GCP_APP_PLAN_SA`, `GCP_DEPLOYER_SA`, `GCP_STATE_BUCKET`, `GCP_IMAGE_REPOSITORY`) are **repository variables**, not variables of the Environment `production`. Reason: the runbook limits that Environment to deployment branches = `main`, and a pull request from a branch could then not read its variables, so `app-plan.yml` would never run. Only `deploy.yml` uses `environment: production`, which keeps the branch gate for deploys. ADR-0009 says the Environment holds the variables; if the owner prefers that, `app-plan.yml` needs a second Environment (e.g. `plan`) without a branch rule.
- Step 5: the bootstrap guard is a composite action that takes the variables as inputs (composite actions cannot read the `vars` context). It checks six values: the service account differs per workflow. Tested locally on all empty (green notice, `ready=false`), partly set (fails naming the empty ones) and all set (`ready=true`).
- Step 5: `deploy.yml` builds `…/jobfinder:<sha>`, pushes it and deploys the pushed digest; Ready is read with `gcloud run services describe` (`latestCreatedRevisionName == latestReadyRevisionName` and `Ready=True`, 5 min). `app-plan.yml` skips fork pull requests with `if`. `ci.yml` installs Terraform with the same script and runs `terraform fmt -check` and, per layer, `init -backend=false` and `validate`; `scripts/lint.sh` runs `terraform fmt -check` when Terraform is installed (required when `CI` is set). `google-github-actions/auth` is pinned to the commit of v3.0.0.
- Step 5: the workflows cannot be run here (no GitHub Actions, no GCP); they are checked with a YAML parse, shellcheck of every `run` block and the guard test. The first real runs are the evidence.

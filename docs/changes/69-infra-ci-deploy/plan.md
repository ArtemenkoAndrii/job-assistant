# Plan: Infrastructure and CI deploy (skeleton 1/3)

| | |
|---|---|
| **Issue** | #69 |
| **Spec** | [spec.md](spec.md) |
| **Status** | Approved |
| **Date** | 2026-11-26 |

## Context

Nothing deploys yet. The ADRs (0005–0009) are unproven until a build reaches Cloud Run from `main` without keys. Existing pieces reused: `/health` in `apps/jobfinder/src/jobfinder/web/app.py`, worker stub `jobfinder/worker/__main__.py` (exits 0), `apps/jobfinder/Dockerfile` (uvicorn, `$PORT`), `ci.yml` (job `ci`, SHA-pinned actions, gitleaks install via `.devcontainer/install-gitleaks.sh`), `scripts/lint.sh` `run` helper, `.gitignore` already ignores `*.tfstate*`, `.terraform/`, `*.tfvars`. No application code changes are needed.

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
4. **`infra/app`**: web service `jobfinder-web` (`iap_enabled`, `ingress` all, min 0/max 2, 1 vCPU/512 MiB, `startup_cpu_boost`, startup probe `GET /health`, env `PORT` default, runs as `web`), `google_cloud_run_v2_service_iam_member` `run.invoker` for the IAP service agent only; job `jobfinder-worker` (1 task, parallelism 1, timeout `7200s`, `max_retries = 0`, 1 vCPU/1 GiB, `python -m jobfinder.worker`, runs as `worker`); Scheduler `30 * * * *` calling the job `:run` as `scheduler`; invoker bindings on the job for `web` and `scheduler`; the IAP agent's address is built from the project number, which the app layer takes from the Environment variable (`app-plan` has no `resourcemanager.projects.get`); image variable is a full digest reference (validated by a `validation` block, so a tag is rejected). No composite indexes (comment says why). Commit.
5. **Workflows** (actions pinned by commit SHA resolved with `gh api`, permissions minimal, `persist-credentials: false`):
   - `bootstrap-guard` composite action (used first in `deploy.yml`, `app-plan.yml`, `drift.yml`): all Environment variables empty → output `ready=false` and `::notice::bootstrap not done, see runbook`, exit 0; all set → `ready=true`; some set and some empty → fail with the names of the empty ones. Later steps run only `if: steps.guard.outputs.ready == 'true'`.
   - `ci.yml`: no cloud access.
   - `app-plan.yml`: `permissions: id-token: write, contents: read, pull-requests: read`; `google-github-actions/auth` with the Environment variables; `terraform init -backend-config=bucket=...`, `plan -lock=false -input=false -var image=<deployed digest>`. The digest is read with `gcloud run services describe jobfinder-web` (resolved to `repo@sha256:…`), so the plan shows no image diff and passes validation; if the service does not exist yet, a fixed all-zero digest is used. Skipped on fork PRs by design (no token).
   - `deploy.yml`: `on: push` to `main`, paths `infra/app/**`, `apps/**`; `environment: production`; `concurrency: { group: deploy, cancel-in-progress: false }`; step 1 is the guard; later steps: auth, `docker build/push` to Artifact Registry, resolve digest (`docker inspect` RepoDigests), `terraform apply -auto-approve -var image=<digest>`, `gcloud run services describe` loop until `Ready=True` on the latest revision (timeout 5 min). No `/health` call.
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

Recorded 2026-11-27 after the bootstrap. Identifiers that the repo keeps out (project number, owner email) are omitted.

| Acceptance criterion | Evidence | Result |
|---|---|---|
| AC1 | `ci.yml` on #72: `terraform fmt -check`, `init -backend=false`, `validate` for both layers, no credentials | ✓ |
| AC2 | `gcloud iam workload-identity-pools providers describe github-actions`: condition `assertion.repository_owner_id == '19709306' && assertion.repository_id == '1464306064'` | ✓ (config inspection) |
| AC3 | `app-plan` on #75 ([run](https://github.com/ArtemenkoAndrii/job-assistant/actions/runs/46024039140)) authenticated as `app-plan` and planned one change (startup probe path); project ID masked as `***` | ✓ |
| AC4 | `drift` by hand after #76 ([run](https://github.com/ArtemenkoAndrii/job-assistant/actions/runs/46025813954)): "No changes". The run before #76 ([run](https://github.com/ArtemenkoAndrii/job-assistant/actions/runs/46025221978)) failed on a real difference (a stale output), which also shows the red path | ✓ |
| AC5 | `deploy` [run](https://github.com/ArtemenkoAndrii/job-assistant/actions/runs/45863025991) attempt 3: image pushed by digest, `Apply complete`, revision `jobfinder-web-00002` Ready; later deploys of #75 and #76 green | ✓ |
| AC6 | `gcloud iam service-accounts get-iam-policy deployer`: only `principalSet://…/attribute.deploy_trigger/push:ArtemenkoAndrii/job-assistant/.github/workflows/deploy.yml@refs/heads/main` | ✓ (config inspection) |
| AC7 | gitleaks in CI on every PR: no leaks; Environment variables hold identifiers only, no secrets; project ID masked in logs | ✓ |
| AC8 | anonymous `curl -sI …/health` → `302` to `accounts.google.com`, `x-goog-iap-generated-response: true`; `run.invoker` on `jobfinder-web` only for the IAP service agent | ✓ |
| AC9 | owner opened `/health` through IAP: `{"status":"ok","version":"0.1.0"}` | ✓ |
| AC10 | `tests/scripts/test_check_infra.py` | ✓ |
| AC11 | owner applied `infra/platform` (78 resources), migrated the state to the bucket, re-applied after #74 (1 added, 2 destroyed, as planned) | ✓ |
| AC12 | `gcloud secrets versions list`: `a1-client-id`, `a1-client-secret`, `openai-api-key`, `email-sender` have 0 versions; `owner-email` holds the owner's value (runbook step 5) | ✓ |
| AC13 | `gcloud projects get-iam-policy` filtered: `deployer` = `deployerRunIam`, `cloudscheduler.admin`, `datastore.indexAdmin`, `run.developer`; `app-plan` = `cloudscheduler.viewer`, `iam.serviceAccountViewer`, `run.viewer`. No project IAM, data, secret or billing role | ✓ |
| AC14 | runbook order: IAP client (step 4) before the first deploy re-run (step 8) | ✓ |
| AC15 | after 15 min idle, the first `/health` took **4.04 s** (request log `httpRequest.latency`; warm: 3 ms). Image **58 MB** (Artifact Registry `imageSizeBytes` 57,980,434) | ✓ (≤ 10 s) |
| AC16 | `gcloud run jobs execute jobfinder-worker --wait`: "successfully completed" | ✓ |
| AC17 | `deploy` [run](https://github.com/ArtemenkoAndrii/job-assistant/actions/runs/45857434820) triggered by merging #72: green, notice "bootstrap not done" | ✓ |
| AC18 | the re-run of the latest `deploy` run kept `push` on `main`; WIF accepted `deployer` (attempts 2 and 3 of [run](https://github.com/ArtemenkoAndrii/job-assistant/actions/runs/45863025991)) | ✓ |
| AC19 | **accepted by the owner on 2026-11-27 without the two-hour observation.** Evidence so far: the Scheduler job exists and calls the job as `scheduler`; its attempts before 16:13 UTC+1 failed with `code=7` because the invoker binding was only applied then | accepted |
| AC20 | Claude Code in the rebuilt dev container: `terraform version` 1.17.2, `init -backend=false` and `validate` pass for both layers | ✓ |

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
- Step 5, owner decision: the non-secret identifiers are variables of **two Environments**, as ADR-0009 says. `production` (deployment branches = `main` only) is used by `deploy.yml` and holds the six values including `GCP_DEPLOYER_SA`. `plan` (no branch restriction, no secrets) is used by `app-plan.yml` and `drift.yml` and holds the six values including `GCP_APP_PLAN_SA`. Reason for the second Environment: a branch restriction on `production` would stop pull requests from reading its variables. (First implemented as repository variables; changed in the pre-merge review.) The guard runs per Environment: all six empty is a green notice, a mix fails naming the empty ones.
- Step 5: the bootstrap guard is a composite action that takes the variables as inputs (composite actions cannot read the `vars` context). It checks six values: the service account differs per workflow. Tested locally on all empty (green notice, `ready=false`), partly set (fails naming the empty ones) and all set (`ready=true`).
- Step 5: `deploy.yml` builds `…/jobfinder:<sha>`, pushes it and deploys the pushed digest; Ready is read with `gcloud run services describe` (`latestCreatedRevisionName == latestReadyRevisionName` and `Ready=True`, 5 min). `app-plan.yml` skips fork pull requests with `if`. `ci.yml` installs Terraform with the same script and runs `terraform fmt -check` and, per layer, `init -backend=false` and `validate`; `scripts/lint.sh` runs `terraform fmt -check` when Terraform is installed (required when `CI` is set). `google-github-actions/auth` is pinned to the commit of v3.0.0.
- Step 5: the workflows cannot be run here (no GitHub Actions, no GCP); they are checked with a YAML parse, shellcheck of every `run` block and the guard test. The first real runs are the evidence.
- Step 6: `docs/runbooks/bootstrap.md` written (nine steps, measurements, operating, rollback by `terraform apply -var image=<old digest>` in Cloud Shell, since `deploy.yml` always builds a new image). Its commands come from documentation and are untested; the runbook says so, and the first person to run a step fixes the text. The runbook lists which values go into which Environment. `CLAUDE.md`, `README.md`, `docs/dev-environment.md` and `docs/architecture.md` updated; the ADR index is unchanged (no ADR was added).
- Review after the first CI run: `install-terraform.sh` and `check_infra.py` were committed as mode 100644 and CI failed with exit 126; both are now executable (`git update-index --chmod=+x`). Checked the other scripts: they are 100755 or run through `bash`/`python3`.
- The secret `email-api-key` is renamed `email-sender` (ADR-0010: JSON with client id, client secret, refresh token, sender address) in `secrets.tf` and the runbook. The platform plan changes accordingly before the first apply.
- The bootstrap guard masks the project ID, project number and state bucket (`::add-mask::`) before anything else; logs of a public repository are public.
- `app-plan.yml` and `drift.yml` use the all-zero digest only when `gcloud` reports the service as not found (`NOT_FOUND` or "Cannot find service"); any other error fails the step, as does a deployed image without a digest. Tested with a fake `gcloud` (found, not found, permission denied, tag).
- The PR body is kept in `pr-69.md` in the repo root, untracked (not committed).

**First platform apply (2026-11-26)**, found by the owner in Cloud Shell:

- GCP account IDs must be 6-30 characters, so `web` failed; the web app's account is now `web-app` (the role keeps the name `web` in the ADRs and in Terraform keys).
- Cloud Shell has no Terraform: the runbook installs the pinned version with `install-terraform.sh`.
- `init -backend=false` does not allow plan/apply with a `backend "gcs"` block: the runbook uses a git-ignored `backend_override.tf` (local backend) for the first apply, removed before `-migrate-state`.
- Custom roles depend on the API enablement; a fresh custom role may need a second apply while IAM propagates (runbook).

**First deploy (2026-11-27)**:

- `deployer` was denied `run.services.setIamPolicy` and `run.jobs.setIamPolicy`: Cloud Run does not support resource-name IAM conditions. The custom role is now granted at project level without a condition ([ADR-0012](../../adr/0012-deployer-cloud-run-iam.md)).
- The OAuth app stays in **Testing** with the owner as test user: *Publish app* needs a homepage and privacy policy on a verified domain. Deviates from ADR-0008's "In production"; runbook updated.
- The health route is `/health`, not `/healthz`: Cloud Run's front end reserves paths ending in `z` and answered a Google 404 before the request reached the container (Cloud Run known issues). ADR-0008 names `/healthz` as the route without the owner check; that route is now `/health`, same rule.
- The first manual `drift.yml` run failed on an output only: `latest_ready_revision` is recorded at apply time, before the new revision is Ready, and `-detailed-exitcode` counts output changes. The output is removed (nothing used it; `deploy.yml` waits with `gcloud`).
- AC19 accepted by the owner without the two-hour observation (see Proof).

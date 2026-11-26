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
| `infra/platform/*.tf` | new: `versions.tf`, `variables.tf`, `apis.tf`, `state.tf`, `wif.tf`, `iam.tf`, `firestore.tf`, `storage.tf`, `secrets.tf`, `registry.tf`, `logging.tf`, `budget.tf`, `firebase.tf`, `outputs.tf`, `terraform.tfvars.example`, `.terraform.lock.hcl` |
| `infra/app/*.tf` | new: `versions.tf` (empty GCS backend, bucket via `-backend-config`), `variables.tf`, `cloud_run_web.tf` (IAP on, invoker for IAP agent, startup probe), `cloud_run_worker.tf`, `scheduler.tf`, `outputs.tf`, `.terraform.lock.hcl` |
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
| `docs/adr/0008-user-authentication.md` | header note row — already committed |

Not touched: `apps/jobfinder/**`, Dockerfile of the app.

## Steps
Each step is a commit; run `scripts/build.sh`, `scripts/lint.sh`, `scripts/test.sh` before each (with `UV_CACHE_DIR` set if the sandbox cache is read-only).

1. **Save plan.md** (this plan). Commit.
2. **Tooling:** `install-terraform.sh`, Dockerfile, allowed domains, `infra/.terraform-version`; `check_infra.py` + tests + lint/test wiring (test first: failing fixture, then the check). Commit.
3. **`infra/platform`**, in this order, each file small:
   - `variables.tf`: `project_id`, `project_number`, `region` (default `us-central1`), `billing_account` (sensitive), `owner_email` (sensitive), `github_repository_id` and `github_owner_id` (defaults are the numeric IDs already public in ADR-0009), `state_bucket`, `files_bucket`, `budget_amount` (5). Real values go in a gitignored `terraform.tfvars` in Cloud Shell; `terraform.tfvars.example` has placeholders only.
   - `apis.tf` (run, cloudscheduler, firestore, secretmanager, artifactregistry, iam, iamcredentials, sts, iap, firebase, billingbudgets, storage, logging); `state.tf` (versioned, private bucket, `prevent_destroy`); `wif.tf` (pool `github`, provider `github-actions`, attribute condition on numeric IDs, mapped `event_name`, `ref`, `workflow_ref`).
   - `iam.tf`: service accounts `web`, `worker`, `scheduler`, `app-plan`, `deployer`; every role of ADR-0006/0009 (custom roles for `storage.objects.list` and for the two `setIamPolicy` permissions); principal bindings: `app-plan` ← any run of the repo; `deployer` ← `workflow_ref` of `deploy.yml@refs/heads/main` and `event_name == 'push'`; owner `iap.httpsResourceAccessor` at project level; IAM conditions for state-bucket prefixes.
   - `firestore.tf` (Native, `us-central1`, TTL on `expire_at` for the TTL collections, daily backup schedule with 7-day retention, rules file denying all client access); `storage.tf` (uniform access, public access prevention, soft delete 7 days, lifecycle `packages/pending/` age 90); `secrets.tf` (5 secrets as containers + accessor bindings per ADR-0006 identities, **no `google_secret_manager_secret_version`**); `registry.tf` (cleanup keep last 3); `logging.tf` (30-day `_Default` retention); `budget.tf` ($5, thresholds 0.5/0.9/1.0, email to the owner); `firebase.tf`; `outputs.tf` (non-secret identifiers the owner pastes into the GitHub Environment).
   - Validate with `terraform init -backend=false && terraform validate`, `fmt`. Commit.
4. **`infra/app`**: web service `jobfinder-web` (`iap_enabled`, `ingress` all, min 0/max 2, 1 vCPU/512 MiB, `startup_cpu_boost`, startup probe `GET /healthz`, env `PORT` default, runs as `web`), `google_cloud_run_v2_service_iam_member` `run.invoker` for the IAP service agent only; job `jobfinder-worker` (1 task, parallelism 1, timeout `7200s`, `max_retries = 0`, 1 vCPU/1 GiB, `python -m jobfinder.worker`, runs as `worker`); Scheduler `30 * * * *` calling the job `:run` as `scheduler`; invoker bindings on the job for `web` and `scheduler`; image variable is a full digest reference (validated by a `validation` block, so a tag is rejected). No composite indexes (comment says why). Commit.
5. **Workflows** (actions pinned by commit SHA resolved with `gh api`, permissions minimal, `persist-credentials: false`):
   - `ci.yml`: no cloud access.
   - `app-plan.yml`: `permissions: id-token: write, contents: read, pull-requests: read`; `google-github-actions/auth` with the Environment variables; `terraform init -backend-config=bucket=...`, `plan -lock=false -input=false`. Skipped on fork PRs by design (no token).
   - `deploy.yml`: `on: push` to `main`, paths `infra/app/**`, `apps/**`; `environment: production`; step 1 `guard` reads the variables and exits 0 with `::notice::bootstrap not done, see runbook` and `ready=false` if any is empty; later steps `if: steps.guard.outputs.ready == 'true'`: auth, `docker build/push` to Artifact Registry, resolve digest (`docker inspect` RepoDigests), `terraform apply -auto-approve -var image=<digest>`, `gcloud run services describe` loop until `Ready=True` on the latest revision (timeout 5 min). No `/healthz` call.
   - `drift.yml`: `schedule: weekly` (+ no `workflow_dispatch`), plan with `-detailed-exitcode`, exit 2 → fail.
   Commit.
6. **Runbook + docs** (R5): numbered owner steps, each with the exact command; ordering note that the IAP client exists before the re-run; last step "Re-run latest `deploy.yml`"; monthly platform plan; rollback by digest; a "what each secret value is and when to add it" table. Update the docs listed above; check Markdown links with `scripts/lint.sh`. Commit.
7. **Verifier:** run the `verifier` subagent with `#69`, quote PASS in the PR; push the branch and open the PR `Closes #69` (owner reviews; squash-merge).
8. **After merge, owner bootstraps** (I assist, cannot touch GCP: the sandbox has no credentials). Merge triggers `deploy.yml` → green "bootstrap not done" (AC17). Owner follows the runbook; re-run (AC18). Measurements (cold start, image size, AC15/19) are pasted into Proof in a short follow-up PR; the issue closes when they are recorded.

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
| AC13 | `gcloud projects get-iam-policy` filtered by the two accounts |
| AC14 | runbook order reviewed in the PR |
| AC15 | Cloud Run `container/startup_latencies` and request log latency after 15 min idle; **value recorded here**: _to fill_; image size from `docker images` / Artifact Registry: _to fill_ |
| AC16 | `gcloud run jobs execute jobfinder-worker --wait`, exit 0 |
| AC17 | the `deploy.yml` run triggered by the merge: green with "bootstrap not done" |
| AC19 | Cloud Run job execution list after 2 h: executions at :30, all succeeded |
| AC20 | `terraform version` and `init -backend=false && validate` output from the rebuilt dev container |

## Divergence log

_Filled during implementation._

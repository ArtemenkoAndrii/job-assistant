# Runbook: bootstrap and operate the deployment

For the owner. Context: [ADR-0009](../adr/0009-infrastructure-as-code.md), [spec](../changes/69-infra-ci-deploy/spec.md), [plan](../changes/69-infra-ci-deploy/plan.md). Replace `<…>` with your own values. **Never commit them:** this repository is public, and so are its CI logs.

> The commands below were written from the documentation and have not been run against a real project. Whoever runs a step first fixes the text here in the same PR.

## Order matters

Merging the PR that adds the workflows triggers `deploy.yml` before anything exists. It ends green with the notice "bootstrap not done, see docs/runbooks/bootstrap.md" and does nothing (all variables empty). When all steps below are done, re-run it (step 8). If only some variables are set, the workflows fail on purpose and name the empty ones.

## One-time steps

### 1. Project and billing

```bash
gcloud projects create job-finder-<suffix> --name="job-finder"
gcloud billing projects link job-finder-<suffix> --billing-account=<billing-account-id>
gcloud config set project job-finder-<suffix>
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com
```

Terraform enables the other APIs itself, but it needs these two first. Use region `us-central1` for everything.

### 2. Firebase terms

In the [Firebase console](https://console.firebase.google.com) choose *Add project* and select `job-finder-<suffix>`. This accepts the Firebase terms; Terraform links the project afterwards. Do not enable Analytics.

### 3. Apply the platform layer (Cloud Shell)

Cloud Shell is already signed in as you and has `gcloud` and Terraform, so no key exists anywhere.

```bash
git clone https://github.com/ArtemenkoAndrii/job-assistant.git
cd job-assistant/infra/platform
cp terraform.tfvars.example terraform.tfvars   # edit: project, billing account, your Google account, bucket names
terraform init -backend=false                  # first apply uses local state: the state bucket does not exist yet
terraform plan
terraform apply
```

If the first apply fails because an API was not enabled yet, wait a minute and apply again. The budget API is called with your user credentials; the provider block already sets `user_project_override` and `billing_project`.

Then move the state into the bucket Terraform just created, and re-initialise:

```bash
terraform output state_bucket
terraform init -migrate-state -backend-config="bucket=<state-bucket>"   # answer yes
terraform plan                                                          # expect: No changes
rm -f terraform.tfstate terraform.tfstate.backup terraform.tfvars
rm -rf .terraform
```

Nothing should stay in the Cloud Shell home: the state is remote, and `terraform.tfvars` holds your email and billing account. For later platform runs, recreate `terraform.tfvars` and `terraform init -backend-config="bucket=<state-bucket>"`, then delete it again.

Keep the outputs for step 6: `terraform output`.

### 4. IAP OAuth client (before the first deploy)

IAP is switched on for `jobfinder-web` by the app layer, so the OAuth client must exist first.

1. Console → *Google Auth Platform* (OAuth consent screen): audience **External**, publishing status **In production** (IAP asks only for basic profile and email, which need no verification; "Testing" would sign you out often).
2. *Clients* → *Create client* → type *Web application*. Add the authorised redirect URI `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect` (edit the client after creation, when the ID is known).
3. Attach the client to IAP at project level. The client secret stays with IAP: it never goes into Terraform, state or the repo.

```bash
cat > "$HOME/iap-settings.yaml" <<'YAML'
access_settings:
  oauth_settings:
    client_id: <CLIENT_ID>
    client_secret: <CLIENT_SECRET>
YAML
gcloud iap settings set "$HOME/iap-settings.yaml" --project=job-finder-<suffix>
rm "$HOME/iap-settings.yaml"
```

The owner's IAP access (`roles/iap.httpsResourceAccessor`) and the IAP service agent are already created by the platform layer.

### 5. Secret values

The platform layer creates five empty secrets. Add a value only when a slice needs it, with `gcloud`, so it never passes through the repo, CI or any state:

```bash
printf '%s' '<value>' | gcloud secrets versions add <secret-id> --data-file=- --project=job-finder-<suffix>
```

| Secret | Value | Needed from |
|---|---|---|
| `owner-email` | your Google account, lower case | #70 (the app's owner check) |
| `a1-client-id`, `a1-client-secret` | A-1 service token (Cloudflare Access) | the A-1 slice |
| `openai-api-key` | OpenAI API key | the first LLM step |
| `email-api-key` | the sender's OAuth secret (ADR-0010) | email delivery |

Rotation (NFR-S5): add a new version, then destroy the old one, so the free six active versions are not exceeded.

### 6. GitHub: Environment and variables

1. Repository *Settings → Environments → New environment* `production`. *Deployment branches and tags*: **Selected branches**, add `main` only. No secrets, no reviewers needed.
2. Set these **repository variables** (non-secret identifiers; they are not variables of the Environment, so that pull requests can read them for `app-plan.yml`):

| Variable | Value |
|---|---|
| `GCP_PROJECT_ID` | `job-finder-<suffix>` |
| `GCP_PROJECT_NUMBER` | `terraform output project_number` |
| `GCP_WIF_PROVIDER` | `terraform output wif_provider` |
| `GCP_APP_PLAN_SA` | `terraform output app_plan_service_account` |
| `GCP_DEPLOYER_SA` | `terraform output deployer_service_account` |
| `GCP_STATE_BUCKET` | `terraform output state_bucket` |
| `GCP_IMAGE_REPOSITORY` | `terraform output image_repository` |

```bash
gh variable set GCP_PROJECT_ID --body "<value>"   # and the same for each of the others
```

Set all seven in one sitting: with some set and some empty, the workflows fail on purpose.

### 7. Check the guardrails (optional but recommended)

```bash
gcloud iam workload-identity-pools providers describe github-actions --workload-identity-pool=github --location=global --project=job-finder-<suffix>
gcloud iam service-accounts get-iam-policy deployer@job-finder-<suffix>.iam.gserviceaccount.com --project=job-finder-<suffix>
```

Expected: the provider's attribute condition names the numeric owner and repository IDs; `deployer` can be used only by the `deploy.yml@refs/heads/main` `push` principal. Paste both outputs into the PR as evidence (AC2, AC6). They contain no secret.

### 8. First deploy: re-run the workflow

```bash
gh run list --workflow deploy.yml --limit 1
gh run rerun <run-id>
```

A re-run keeps the `push` event and the `main` ref, so WIF accepts `deployer`. The run builds and pushes the image, applies `infra/app` with the image digest, and waits until the new revision is Ready (Cloud Run's startup probe on `/healthz`). It does not call `/healthz` itself: the service is behind IAP.

### 9. Check by hand

Open the service URL (`gcloud run services describe jobfinder-web --region us-central1 --format='value(status.url)'`) at `/healthz` in a browser signed in as the owner. Expected: `{"status":"ok","version":"…"}`. A different Google account, or none, must be stopped by IAP.

## Measurements (AC15, AC16, AC19)

- **Cold start:** wait until the service has had no request for 15 minutes (it scales to zero), then open `/healthz` once. Read the time from *Cloud Run → jobfinder-web → Metrics → Container startup latency* and from the request log (`httpRequest.latency`). Target ≤ 10 s (NFR-A1).
- **Image size:** `gcloud artifacts docker images list us-central1-docker.pkg.dev/job-finder-<suffix>/jobfinder --include-tags --format='table(package,version,metadata.imageSizeBytes)'`.
- **Worker:** `gcloud run jobs execute jobfinder-worker --region us-central1 --wait` exits 0; after two hours the execution list shows one per hour at minute 30, all succeeded.

Record the values in `docs/changes/69-infra-ci-deploy/plan.md` → Proof.

## Operating

- **App changes** go through a PR; merging to `main` runs `deploy.yml`. PRs that touch `apps/**` or `infra/app/**` get a read-only plan from `app-plan.yml`.
- **Drift:** `drift.yml` runs weekly (and by hand: *Actions → drift → Run workflow*) and fails on any difference in the app layer.
- **Platform changes** go through a PR and your apply in Cloud Shell, as in step 3 (init with the bucket, plan, apply, delete the local files). Run `terraform plan` of the platform layer **once a month** and after every platform change; it must say *No changes*. CI does not do this, because it would need read access to IAM, data and billing (recorded exception to NFR-M3).
- **Rollback to a previous image** (the registry keeps the last three): find the digest with the `gcloud artifacts docker images list` command above, then in Cloud Shell:

  ```bash
  cd job-assistant/infra/app
  terraform init -backend-config="bucket=<state-bucket>"
  terraform apply -var project_id=job-finder-<suffix> -var project_number=<project-number> \
    -var image=us-central1-docker.pkg.dev/job-finder-<suffix>/jobfinder/jobfinder@sha256:<digest>
  ```

  Then fix the cause on `main`; the next deploy replaces the rollback.
- **Budget:** alerts go to you at 50%, 90% and 100% of $5 a month (NFR-C1).

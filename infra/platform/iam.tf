# Service accounts and every role they get (ADR-0006, ADR-0009). CI accounts never hold rights over
# IAM, data or secret values.
locals {
  # Key: the role name used in the ADRs and below. id: the GCP account ID, which must be 6-30
  # characters, so the web app's account is `web-app`.
  service_accounts = {
    web       = { id = "web-app", name = "Job Finder web app (Cloud Run service)" }
    worker    = { id = "worker", name = "Job Finder run worker (Cloud Run job)" }
    scheduler = { id = "scheduler", name = "Cloud Scheduler: starts the worker job" }
    app-plan  = { id = "app-plan", name = "CI: read-only plan of the app layer" }
    deployer  = { id = "deployer", name = "CI: deploys the app layer from main" }
  }
  state_bucket_app_prefix = "projects/_/buckets/${google_storage_bucket.state.name}/objects/app/"
}

resource "google_service_account" "this" {
  for_each = local.service_accounts

  account_id   = each.value.id
  display_name = each.value.name

  depends_on = [google_project_service.enabled]
}

# --- CI identities (WIF) ---

resource "google_service_account_iam_member" "app_plan_wif" {
  service_account_id = google_service_account.this["app-plan"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.principal_app_plan
}

resource "google_service_account_iam_member" "deployer_wif" {
  service_account_id = google_service_account.this["deployer"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.principal_deployer
}

# Names only: lets the CI accounts list the state bucket (needed by `terraform init`); the
# contents of platform/ stay unreadable because object access is limited to app/ below.
resource "google_project_iam_custom_role" "state_lister" {
  role_id     = "stateLister"
  title       = "Terraform state lister"
  description = "List object names in the state bucket"
  permissions = ["storage.objects.list"]

  depends_on = [google_project_service.enabled]
}

resource "google_storage_bucket_iam_member" "state_lister" {
  for_each = toset(["app-plan", "deployer"])

  bucket = google_storage_bucket.state.name
  role   = google_project_iam_custom_role.state_lister.id
  member = "serviceAccount:${google_service_account.this[each.key].email}"
}

resource "google_storage_bucket_iam_member" "app_plan_state_read" {
  bucket = google_storage_bucket.state.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.this["app-plan"].email}"

  condition {
    title      = "app-state-only"
    expression = "resource.name.startsWith(\"${local.state_bucket_app_prefix}\")"
  }
}

resource "google_storage_bucket_iam_member" "deployer_state_write" {
  bucket = google_storage_bucket.state.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.this["deployer"].email}"

  condition {
    title      = "app-state-only"
    expression = "resource.name.startsWith(\"${local.state_bucket_app_prefix}\")"
  }
}

# app-plan: read-only. No data, secret, IAM-admin or platform-state access. `datastore.indexViewer`
# (ADR-0009) lets it read the composite indexes of the app layer (infra/app/indexes.tf, #71); without
# it app-plan and drift fail with permission denied once an index exists.
resource "google_project_iam_member" "app_plan" {
  for_each = toset([
    "roles/run.viewer",
    "roles/cloudscheduler.viewer",
    "roles/datastore.indexViewer",
    "roles/iam.serviceAccountViewer",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.this["app-plan"].email}"
}

# deployer: deploys the service, the job and the scheduler job; no project IAM, data, secret-value
# or billing rights.
resource "google_project_iam_member" "deployer" {
  for_each = toset([
    "roles/run.developer",
    "roles/cloudscheduler.admin",
    "roles/datastore.indexAdmin",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.this["deployer"].email}"
}

resource "google_service_account_iam_member" "deployer_act_as" {
  for_each = toset(["web", "worker", "scheduler"])

  service_account_id = google_service_account.this[each.key].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.this["deployer"].email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.this["deployer"].email}"
}

# Who may invoke the service and the job is set by Terraform in the app layer, so deployer needs the
# IAM-policy permissions of Cloud Run. Granted at project level without a condition: Cloud Run does not
# support resource-name conditions, and the resources do not exist when this layer runs (ADR-0012).
resource "google_project_iam_custom_role" "deployer_run_iam" {
  role_id     = "deployerRunIam"
  title       = "Deployer: Cloud Run IAM policy"
  description = "Read and set the IAM policy of the Job Finder service and job"
  permissions = [
    "run.services.getIamPolicy",
    "run.services.setIamPolicy",
    "run.jobs.getIamPolicy",
    "run.jobs.setIamPolicy",
  ]

  depends_on = [google_project_service.enabled]
}

resource "google_project_iam_member" "deployer_run_iam" {
  project = var.project_id
  role    = google_project_iam_custom_role.deployer_run_iam.id
  member  = "serviceAccount:${google_service_account.this["deployer"].email}"
}

# --- Runtime identities ---

# Data access (ADR-0007). Secret access is bound per secret in secrets.tf.
resource "google_project_iam_member" "runtime_firestore" {
  for_each = toset(["web", "worker"])

  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.this[each.key].email}"
}

resource "google_storage_bucket_iam_member" "runtime_files" {
  for_each = toset(["web", "worker"])

  bucket = google_storage_bucket.files.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.this[each.key].email}"
}

# --- The owner ---

# One IAP-protected resource, so project level is equivalent to the service-level grant of ADR-0008
# and keeps the owner's email out of the app layer (ADR-0009).
resource "google_project_iam_member" "owner_iap" {
  project = var.project_id
  role    = "roles/iap.httpsResourceAccessor"
  member  = "user:${var.owner_email}"
}

# The IAP service agent exists before the app layer grants it run.invoker (ADR-0008).
resource "google_project_service_identity" "iap" {
  provider = google-beta
  project  = var.project_id
  service  = "iap.googleapis.com"

  depends_on = [google_project_service.enabled]
}

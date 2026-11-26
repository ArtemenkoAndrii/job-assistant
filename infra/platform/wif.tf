# Workload Identity Federation for GitHub Actions: no keys anywhere (NFR-S4, ADR-0009).
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions"

  # Numeric IDs of the owner and the repository: nothing else can get a token.
  attribute_condition = "assertion.repository_owner_id == '${var.github_owner_id}' && assertion.repository_id == '${var.github_repository_id}'"

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.event_name"    = "assertion.event_name"
    "attribute.ref"           = "assertion.ref"
    "attribute.workflow_ref"  = "assertion.workflow_ref"
    # A principalSet matches one attribute, so deployer's two conditions (workflow file on main and
    # the push event) are combined into one value.
    "attribute.deploy_trigger" = "assertion.event_name + ':' + assertion.workflow_ref"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

locals {
  wif_pool = google_iam_workload_identity_pool.github.name

  # Every run of this repository (pull requests from its branches) may use app-plan.
  principal_app_plan = "principalSet://iam.googleapis.com/${local.wif_pool}/attribute.repository_id/${var.github_repository_id}"

  # Only deploy.yml on main, started by a push, may use deployer.
  principal_deployer = "principalSet://iam.googleapis.com/${local.wif_pool}/attribute.deploy_trigger/push:${local.repository}/.github/workflows/deploy.yml@refs/heads/main"
}

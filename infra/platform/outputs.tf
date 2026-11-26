# Non-secret identifiers for the GitHub Environment `production` variables (ADR-0009) and the runbook.
output "project_number" {
  value = local.project_number
}

output "wif_provider" {
  description = "Full name of the WIF provider, for google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

output "app_plan_service_account" {
  value = google_service_account.this["app-plan"].email
}

output "deployer_service_account" {
  value = google_service_account.this["deployer"].email
}

output "image_repository" {
  description = "Docker repository for the app image."
  value       = "${google_artifact_registry_repository.images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "state_bucket" {
  value = google_storage_bucket.state.name
}

output "iap_service_agent" {
  description = "Gets run.invoker on jobfinder-web in the app layer."
  value       = google_project_service_identity.iap.email
}

resource "google_artifact_registry_repository" "images" {
  repository_id = "jobfinder"
  location      = var.region
  format        = "DOCKER"
  description   = "Job Finder container images"

  # Keep the last 3 versions (ADR-0006), delete the rest.
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-last-3"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  cleanup_policies {
    id     = "delete-older"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "3600s"
    }
  }

  depends_on = [google_project_service.enabled]
}

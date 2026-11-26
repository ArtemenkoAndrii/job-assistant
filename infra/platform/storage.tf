# Private files bucket (ADR-0007): uploads and tailored PDFs; downloads go through the web app.
resource "google_storage_bucket" "files" {
  name                        = var.files_bucket
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  soft_delete_policy {
    retention_duration_seconds = 604800 # 7 days
  }

  # Packages not applied to are deleted after 90 days (NFR-P3). Applied ones live under
  # packages/applied/ and have no rule.
  lifecycle_rule {
    condition {
      age            = 90
      matches_prefix = ["packages/pending/"]
    }
    action {
      type = "Delete"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.enabled]
}

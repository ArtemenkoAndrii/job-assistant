# 30-day log retention (NFR-P3, NFR-P6).
resource "google_logging_project_bucket_config" "default" {
  project        = var.project_id
  location       = "global"
  bucket_id      = "_Default"
  retention_days = 30

  depends_on = [google_project_service.enabled]
}

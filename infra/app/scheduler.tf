# One job, every hour at minute 30, so the default Saturday 01:30 slot is exact (ADR-0006). The worker
# decides which profiles are due and exits in seconds if none are.
resource "google_cloud_scheduler_job" "worker_tick" {
  name      = "jobfinder-worker-tick"
  region    = var.region
  schedule  = "30 * * * *"
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.worker.name}:run"

    oauth_token {
      service_account_email = local.scheduler_sa_email
    }
  }
}

output "service_url" {
  description = "URL of jobfinder-web (behind IAP)."
  value       = google_cloud_run_v2_service.web.uri
}

# No latest_ready_revision output: apply records it before the new revision is Ready, so every
# later plan shows it changed and drift.yml (-detailed-exitcode) would fail after each deploy.

output "worker_job" {
  value = google_cloud_run_v2_job.worker.name
}

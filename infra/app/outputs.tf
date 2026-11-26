output "service_url" {
  description = "URL of jobfinder-web (behind IAP)."
  value       = google_cloud_run_v2_service.web.uri
}

output "latest_ready_revision" {
  value = google_cloud_run_v2_service.web.latest_ready_revision
}

output "worker_job" {
  value = google_cloud_run_v2_job.worker.name
}

# The run worker (ADR-0006): one task, no retries (a blocked run is not retried, NFR-A2), up to 2 h.
resource "google_cloud_run_v2_job" "worker" {
  name                = "jobfinder-worker"
  location            = var.region
  deletion_protection = false

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = local.worker_sa_email
      timeout         = "7200s"
      max_retries     = 0

      containers {
        image   = var.image
        command = ["python"]
        args    = ["-m", "jobfinder.worker"]

        # No secret references: the worker reads its secrets at execution time (#71).
        env {
          name  = "JOBFINDER_ENVIRONMENT"
          value = "production"
        }
        env {
          name  = "JOBFINDER_PROJECT_NUMBER"
          value = var.project_number
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
    }
  }
}

# Who may start the job: the web app ("Run now") and the scheduler.
resource "google_cloud_run_v2_job_iam_binding" "invoker" {
  name     = google_cloud_run_v2_job.worker.name
  location = google_cloud_run_v2_job.worker.location
  role     = "roles/run.invoker"
  members = [
    "serviceAccount:${local.web_sa_email}",
    "serviceAccount:${local.scheduler_sa_email}",
  ]
}

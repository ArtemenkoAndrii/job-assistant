# The web app (ADR-0006): scale to zero, request-based billing, IAP in front (ADR-0008).
resource "google_cloud_run_v2_service" "web" {
  name                = "jobfinder-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  iap_enabled         = true
  deletion_protection = false

  template {
    service_account = local.web_sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      # App settings (ADR-0008). The owner's address comes from Secret Manager, read when an
      # instance starts: a changed value needs the next deploy or an instance restart.
      env {
        name  = "JOBFINDER_ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "JOBFINDER_PROJECT_NUMBER"
        value = var.project_number
      }
      env {
        name = "JOBFINDER_OWNER_EMAIL"
        value_source {
          secret_key_ref {
            secret  = "owner-email"
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      # A revision becomes Ready only when /health answers; deploy.yml waits for that and makes no
      # network call itself (the service is behind IAP).
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 0
        period_seconds        = 2
        timeout_seconds       = 2
        failure_threshold     = 30
      }
    }
  }
}

# Authoritative for run.invoker: only the IAP service agent. Anything else, including allUsers, is
# removed on the next apply and shows as drift.
resource "google_cloud_run_v2_service_iam_binding" "invoker" {
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.invoker"
  members  = [local.iap_agent]
}

terraform {
  required_version = "~> 1.17"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  # The bucket is passed at init time (-backend-config=bucket=...); CI reads and writes only the app/
  # prefix (ADR-0009).
  backend "gcs" {
    prefix = "app"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  # Service accounts are created by the platform layer; their addresses follow from the project ID,
  # so this layer never reads the platform state.
  web_sa_email       = "web-app@${var.project_id}.iam.gserviceaccount.com"
  worker_sa_email    = "worker@${var.project_id}.iam.gserviceaccount.com"
  scheduler_sa_email = "scheduler@${var.project_id}.iam.gserviceaccount.com"

  # The IAP service agent (created by the platform layer) is the only principal that may invoke the
  # service; allUsers never gets a role (ADR-0008).
  iap_agent = "serviceAccount:service-${var.project_number}@gcp-sa-iap.iam.gserviceaccount.com"
}

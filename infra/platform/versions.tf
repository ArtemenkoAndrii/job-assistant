terraform {
  required_version = "~> 1.17"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 8.0"
    }
  }

  # The bucket is passed at init time (-backend-config=bucket=...). The bootstrap starts with
  # `terraform init -backend=false` (local state) and then runs `terraform init -migrate-state`
  # (docs/runbooks/bootstrap.md).
  backend "gcs" {
    prefix = "platform"
  }
}

# user_project_override and billing_project: the budget API is called with the owner's user
# credentials from Cloud Shell and needs a quota project.
provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  project_number = data.google_project.this.number
  repository     = "${var.github_owner}/${var.github_repository}"
}

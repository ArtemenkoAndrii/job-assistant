variable "project_id" {
  description = "GCP project ID (Environment variable GCP_PROJECT_ID)."
  type        = string
}

variable "project_number" {
  description = "GCP project number, for the IAP service agent address (Environment variable)."
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "image" {
  description = "Image reference by digest: <repo>/<name>@sha256:<64 hex>. A tag is rejected, so a deploy is exactly one build."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "image must be referenced by digest (…@sha256:<64 hex>), not by tag."
  }
}

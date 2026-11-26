variable "project_id" {
  description = "GCP project ID (job-finder-<suffix>, ADR-0009 step 1)."
  type        = string
}

variable "region" {
  description = "Region of every regional resource (ADR-0006, NFR-P2)."
  type        = string
  default     = "us-central1"
}

variable "billing_account" {
  description = "Billing account ID for the budget. Kept in the platform state only."
  type        = string
  sensitive   = true
}

variable "owner_email" {
  description = "The owner's Google account: IAP access and budget alerts. Entered in Cloud Shell, never in GitHub."
  type        = string
  sensitive   = true
}

variable "github_owner" {
  description = "GitHub account that owns the repository."
  type        = string
  default     = "ArtemenkoAndrii"
}

variable "github_repository" {
  description = "Repository name."
  type        = string
  default     = "job-assistant"
}

# Numeric IDs, so a renamed or recreated repository cannot be impersonated (ADR-0009).
variable "github_owner_id" {
  type    = string
  default = "19709306"
}

variable "github_repository_id" {
  type    = string
  default = "1464306064"
}

variable "state_bucket" {
  description = "Name of the Terraform state bucket (globally unique)."
  type        = string
}

variable "files_bucket" {
  description = "Name of the private files bucket, job-finder-files-<suffix> (ADR-0007)."
  type        = string
}

variable "budget_amount" {
  description = "Monthly hosting budget in the billing account's currency (NFR-C1)."
  type        = number
  default     = 5
}

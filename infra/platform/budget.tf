# Hosting budget with alerts at 50%, 90% and 100% to the owner (NFR-C1).
resource "google_monitoring_notification_channel" "owner_email" {
  display_name = "Owner email"
  type         = "email"

  labels = {
    email_address = var.owner_email
  }

  depends_on = [google_project_service.enabled]
}

resource "google_billing_budget" "hosting" {
  billing_account = var.billing_account
  display_name    = "Job Finder hosting"

  budget_filter {
    projects = ["projects/${local.project_number}"]
  }

  amount {
    specified_amount {
      units = tostring(var.budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.owner_email.id]
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.enabled]
}

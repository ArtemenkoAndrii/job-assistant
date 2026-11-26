# Secret containers and who may read them (ADR-0006, ADR-0008, ADR-0010; `email-sender` holds the JSON
# with client id, client secret, refresh token and sender address). The values are added by the
# owner with `gcloud secrets versions add`, so they never pass through the repo, CI or any state.
# There is deliberately no google_secret_manager_secret_version here.
locals {
  secrets = {
    "a1-client-id"     = ["worker"]
    "a1-client-secret" = ["worker"]
    "openai-api-key"   = ["web", "worker"]
    "email-sender"     = ["worker"]
    "owner-email"      = ["web"]
  }

  secret_readers = merge([
    for secret, readers in local.secrets : {
      for reader in readers : "${secret}/${reader}" => { secret = secret, reader = reader }
    }
  ]...)
}

resource "google_secret_manager_secret" "this" {
  for_each = local.secrets

  secret_id = each.key

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret_iam_member" "reader" {
  for_each = local.secret_readers

  secret_id = google_secret_manager_secret.this[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.this[each.value.reader].email}"
}

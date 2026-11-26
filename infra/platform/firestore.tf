# Firestore (ADR-0007): Native mode, Standard edition. Client access is denied by the rules; the app
# uses the server SDK with its service account.
resource "google_firestore_database" "default" {
  name                    = "(default)"
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  database_edition        = "STANDARD"
  delete_protection_state = "DELETE_PROTECTION_ENABLED"

  depends_on = [google_project_service.enabled]
}

# TTL on `expire_at` (NFR-P3). An empty index_config exempts the field from indexing.
resource "google_firestore_field" "expire_at" {
  for_each = toset(["runs", "vacancies", "dossiers", "packages", "cost_ledger", "page_loads"])

  database   = google_firestore_database.default.name
  collection = each.value
  field      = "expire_at"

  index_config {}

  ttl_config {}
}

# Daily backup kept 7 days (NFR-A6).
resource "google_firestore_backup_schedule" "daily" {
  database  = google_firestore_database.default.name
  retention = "604800s"

  daily_recurrence {}
}

resource "google_firebaserules_ruleset" "firestore" {
  source {
    files {
      name    = "firestore.rules"
      content = <<-RULES
        rules_version = '2';
        service cloud.firestore {
          match /databases/{database}/documents {
            match /{document=**} {
              allow read, write: if false;
            }
          }
        }
      RULES
    }
  }

  depends_on = [google_firestore_database.default]
}

resource "google_firebaserules_release" "firestore" {
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore.name

  depends_on = [google_firestore_database.default]
}

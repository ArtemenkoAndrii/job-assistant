# Firestore composite indexes belong to this layer (ADR-0009). Both serve the run queue (ADR-0007):
# the oldest queued run, and the latest run of one kind (the "System checks" card, #71).
resource "google_firestore_index" "runs_status_created" {
  project    = var.project_id
  database   = "(default)"
  collection = "runs"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "ASCENDING"
  }
}

resource "google_firestore_index" "runs_kind_created" {
  project    = var.project_id
  database   = "(default)"
  collection = "runs"

  fields {
    field_path = "kind"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }
}

# Links the project to Firebase for console access by the owner (ADR-0007). The Firebase terms are
# accepted by the owner in the Console first (runbook step 2). No client SDK is used.
resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id

  depends_on = [google_project_service.enabled]
}

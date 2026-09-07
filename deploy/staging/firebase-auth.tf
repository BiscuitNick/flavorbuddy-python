# Only verify users and mint sessions; the app cannot administer Firebase users.
resource "google_project_iam_custom_role" "firebase_session" {
  role_id     = "flavorbuddyFirebaseSession"
  title       = "FlavorBuddy Firebase sessions"
  permissions = ["firebaseauth.users.get", "firebaseauth.users.createSession"]
}

resource "google_project_iam_member" "firebase_session" {
  project = var.project
  role    = google_project_iam_custom_role.firebase_session.name
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

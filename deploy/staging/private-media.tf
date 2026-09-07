# Proposed additional infrastructure; applying requires spending approval.
resource "google_storage_bucket" "private_photos" {
  name                        = "${var.project}-staging-private-photos"
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  soft_delete_policy { retention_duration_seconds = 0 }
  lifecycle { prevent_destroy = true }
}
resource "google_storage_bucket_iam_member" "private_runtime" {
  bucket = google_storage_bucket.private_photos.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_job" "housekeeping" {
  name                = "flavorbuddy-staging-housekeeping"
  location            = "us-central1"
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "300s"
      max_retries     = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance { instances = [google_sql_database_instance.staging.connection_name] }
      }
      containers {
        image   = var.image
        command = ["python", "manage.py", "run_housekeeping"]
        resources { limits = { cpu = "1", memory = "512Mi" } }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        dynamic "env" {
          for_each = local.env
          content {
            name  = env.key
            value = env.value
          }
        }
        dynamic "env" {
          for_each = local.secrets
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value
                version = var.secret_versions[env.value]
              }
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.runtime]
}

resource "google_service_account" "scheduler" {
  account_id   = "fb-staging-scheduler"
  display_name = "FlavorBuddy housekeeping scheduler"
}
resource "google_cloud_run_v2_job_iam_member" "scheduler" {
  name     = google_cloud_run_v2_job.housekeeping.name
  location = "us-central1"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
resource "google_cloud_scheduler_job" "housekeeping" {
  name             = "flavorbuddy-staging-housekeeping"
  region           = "us-central1"
  schedule         = "17 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  http_target {
    uri         = "https://run.googleapis.com/v2/projects/${var.project}/locations/us-central1/jobs/${google_cloud_run_v2_job.housekeeping.name}:run"
    http_method = "POST"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode("{}")
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
  depends_on = [google_project_service.apis, google_cloud_run_v2_job_iam_member.scheduler]
}

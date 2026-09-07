terraform {
  # Configure a protected operator path with init -backend-config=path=... .
  # State has no secret values; do not leave it in the checkout or /tmp.
  backend "local" {}
  required_version = ">= 1.5"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 7.0" }
  }
}
provider "google" {
  project = var.project
  region  = "us-central1"
}
variable "project" { default = "flavorbuddy-20260906" }
variable "image" {
  type        = string
  description = "Reviewed Artifact Registry image pinned by sha256 digest"
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Pin the application image by digest."
  }
}
variable "origin" {
  type        = string
  description = "Exact HTTPS staging origin, determined before the first service deployment"
}
variable "invokers" {
  type        = set(string)
  description = "Explicit IAM members allowed to invoke the protected service"
  validation {
    condition     = length(var.invokers) > 0 && alltrue([for m in var.invokers : can(regex("^(user|serviceAccount|group):", m))])
    error_message = "Use explicit users, groups or service accounts; public principals are forbidden."
  }
}
variable "smtp_host" {
  type    = string
  default = ""
}
variable "smtp_user" {
  type    = string
  default = ""
}
variable "from_email" {
  type    = string
  default = "noreply@localhost"
}
# Secret versions and SQL login are populated out of band, so Terraform state
# never contains application, database or SMTP passwords.
variable "secret_versions" {
  type        = map(string)
  description = "Numeric versions for fb-staging-django-key, fb-staging-db-password and fb-staging-smtp-password"
}
resource "google_project_service" "apis" {
  for_each           = toset(["run.googleapis.com", "sqladmin.googleapis.com", "secretmanager.googleapis.com", "artifactregistry.googleapis.com", "cloudscheduler.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}
resource "google_service_account" "runtime" {
  account_id   = "fb-staging-runtime"
  display_name = "FlavorBuddy staging runtime"
}
resource "google_project_iam_member" "sql" {
  project = var.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}
resource "google_artifact_registry_repository" "app" {
  location      = "us-central1"
  repository_id = "flavorbuddy"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}
resource "google_secret_manager_secret" "app" {
  for_each  = toset(["fb-staging-django-key", "fb-staging-db-password", "fb-staging-smtp-password"])
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}
resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = google_secret_manager_secret.app
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}
resource "google_sql_database_instance" "staging" {
  name                = "fb-staging-pg"
  region              = "us-central1"
  database_version    = "POSTGRES_16"
  deletion_protection = true
  settings {
    tier                        = "db-f1-micro"
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    disk_size                   = 10
    disk_type                   = "PD_SSD"
    disk_autoresize             = true
    disk_autoresize_limit       = 20
    deletion_protection_enabled = true
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "05:00"
      transaction_log_retention_days = 7
      backup_retention_settings { retained_backups = 7 }
    }
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
      # No authorized networks. Connect through the authenticated Cloud SQL connector.
    }
  }
  depends_on = [google_project_service.apis]
}
resource "google_sql_database" "app" {
  name     = "flavorbuddy_staging"
  instance = google_sql_database_instance.staging.name
}
locals {
  env = {
    DJANGO_ENV             = "production"
    DJANGO_DEBUG           = "false"
    PROJECT_URL            = var.origin
    DJANGO_ALLOWED_HOSTS   = trimprefix(var.origin, "https://")
    TRUST_PROXY_HTTPS      = "true"
    POSTGRES_HOST          = "/cloudsql/${google_sql_database_instance.staging.connection_name}"
    POSTGRES_DB            = google_sql_database.app.name
    POSTGRES_USER          = "flavorbuddy_staging"
    POSTGRES_SSLMODE       = "disable" # Unix socket is tunneled with TLS by the connector.
    STARTER_IMAGE_STORAGE  = "gcs"
    GS_STARTER_BUCKET_NAME = "flavorbuddy-20260906-starter-images"
    PRIVATE_PHOTO_BACKEND  = "gcs"
    GS_PRIVATE_BUCKET_NAME = google_storage_bucket.private_photos.name
    AI_ENABLED             = "false"
    EMAIL_BACKEND          = var.smtp_host != "" ? "django.core.mail.backends.smtp.EmailBackend" : "django.core.mail.backends.locmem.EmailBackend"
    EMAIL_HOST             = var.smtp_host
    EMAIL_HOST_USER        = var.smtp_user
    DEFAULT_FROM_EMAIL     = var.from_email
  }
  secrets = merge({
    DJANGO_SECRET_KEY = "fb-staging-django-key"
    POSTGRES_PASSWORD = "fb-staging-db-password"
  }, var.smtp_host != "" ? { EMAIL_HOST_PASSWORD = "fb-staging-smtp-password" } : {})
}
resource "google_cloud_run_v2_service" "staging" {
  name                 = "flavorbuddy-staging"
  location             = "us-central1"
  deletion_protection  = true
  invoker_iam_disabled = false
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  template {
    service_account                  = google_service_account.runtime.email
    max_instance_request_concurrency = 8
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance { instances = [google_sql_database_instance.staging.connection_name] }
    }
    containers {
      image = var.image
      ports { container_port = 8000 }
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
      startup_probe {
        tcp_socket { port = 8000 }
      }
    }
  }
  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.runtime, google_storage_bucket_iam_member.private_runtime]
}
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = var.invokers
  name     = google_cloud_run_v2_service.staging.name
  location = "us-central1"
  role     = "roles/run.invoker"
  member   = each.value
}
output "service_uri" { value = google_cloud_run_v2_service.staging.uri }
output "sql_connection" { value = google_sql_database_instance.staging.connection_name }

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required Google Cloud APIs
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com"
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# 2. Artifact Registry Docker Repository
resource "google_artifact_registry_repository" "demo_repo" {
  location      = var.region
  repository_id = "gsis-demo-repo"
  description   = "Docker repository for GSIS Gabay AI Omnichannel Executive Demo"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# 3. Dedicated Least-Privilege Service Account for Cloud Run
resource "google_service_account" "demo_sa" {
  account_id   = "gsis-gabay-demo-sa"
  display_name = "GSIS Gabay AI Executive Demo Runtime Service Account"
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.demo_sa.email}"
}

# 4. Secret Manager JWT Signing Secret
resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "gsis-gabay-demo-jwt-secret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_version" "jwt_secret_v1" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = "gsis-gabay-ai-executive-demo-2026-hmac-sha256-secret"
}

resource "google_secret_manager_secret_iam_member" "jwt_secret_access" {
  secret_id = google_secret_manager_secret.jwt_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.demo_sa.email}"
}

# 5. Cloud Run v2 Service (GSIS Gabay AI Demo)
resource "google_cloud_run_v2_service" "gsis_demo_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.demo_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_REGION"
        value = var.region
      }
      env {
        name  = "GSIS_DEMO_DB_PATH"
        value = "/tmp/gsis_gabay_demo.sqlite3"
      }
      env {
        name = "GSIS_DEMO_JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.demo_repo,
    google_secret_manager_secret_version.jwt_secret_v1,
    google_secret_manager_secret_iam_member.jwt_secret_access
  ]
}

# 6. Allow Unauthenticated Public Executive Demo Access
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.gsis_demo_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

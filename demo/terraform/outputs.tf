output "cloud_run_service_url" {
  description = "Live HTTPS URL of the deployed GSIS Gabay AI Executive Demo on Cloud Run"
  value       = google_cloud_run_v2_service.gsis_demo_service.uri
}

output "artifact_registry_repository" {
  description = "Artifact Registry Docker repository URI"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.demo_repo.repository_id}"
}

output "service_account_email" {
  description = "Dedicated least-privilege Cloud Run Service Account"
  value       = google_service_account.demo_sa.email
}

output "one_command_teardown" {
  description = "Command to cleanly destroy all demo cloud resources"
  value       = "cd demo/terraform && ./teardown.sh"
}

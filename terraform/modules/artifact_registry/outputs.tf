output "repository_url" {
  description = "The URL for pushing Docker images"
  value       = "${var.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repository.repository_id}"
}
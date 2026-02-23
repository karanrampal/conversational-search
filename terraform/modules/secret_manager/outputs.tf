output "secret_ids" {
  description = "The IDs of the created secrets."
  value       = { for k, v in google_secret_manager_secret.secret : k => v.id }
}

output "secret_version_ids" {
  description = "The IDs of the created secret versions."
  value       = { for k, v in google_secret_manager_secret_version.secret_version : k => v.id }
}

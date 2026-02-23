output "url" {
  description = "GS URL of the bucket"
  value       = google_storage_bucket.bucket.url
}

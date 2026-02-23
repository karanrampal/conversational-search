output "repository_url" {
  description = "The URL for artifact registry"
  value       = module.artifact_registry.repository_url
}

output "bucket_url" {
  description = "The URL of the GCS bucket"
  value       = module.cloud_storage.url
}

output "network_name" {
  description = "The name of the VPC network"
  value       = module.network.network_name
}

output "subnet_name" {
  description = "The name of the VPC subnet"
  value       = module.network.subnet_name
}

output "gke_cluster_name" {
  description = "The name of the GKE cluster."
  value       = module.gke_cluster.cluster_name
}

output "qdrant_ilb_ip" {
  description = "The static internal IP address for Qdrant ILB"
  value       = module.network.static_internal_ip
}

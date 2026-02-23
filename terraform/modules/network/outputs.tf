output "network_name" {
  description = "Name of the VPC network"
  value       = google_compute_network.vpc.name
}

output "subnet_name" {
  description = "Name of the VPC subnet"
  value       = google_compute_subnetwork.subnet.name
}

output "pods_range_name" {
  description = "Name of the secondary range for pods"
  value       = google_compute_subnetwork.subnet.secondary_ip_range[0].range_name
}

output "services_range_name" {
  description = "Name of the secondary range for services"
  value       = google_compute_subnetwork.subnet.secondary_ip_range[1].range_name
}

output "static_internal_ip" {
  description = "The static internal IP address"
  value       = google_compute_address.static_internal_ip.address
}

output "psc_subnet_name" {
  description = "Name of the PSC NAT subnet"
  value       = var.psc_subnet_cidr != null ? google_compute_subnetwork.psc_subnet[0].name : null
}

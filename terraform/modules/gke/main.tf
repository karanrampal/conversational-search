resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.location
  project  = var.project_id

  resource_labels = var.labels

  enable_autopilot = true

  network    = var.network
  subnetwork = var.subnetwork

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  control_plane_endpoints_config {
    dns_endpoint_config {
      allow_external_traffic = true
    }
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
  }

  maintenance_policy {
    daily_maintenance_window {
      start_time = "03:00"
    }
  }

  deletion_protection = false
}


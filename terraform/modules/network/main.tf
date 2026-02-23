resource "google_compute_network" "vpc" {
  name                    = var.network_name
  project                 = var.project_id
  auto_create_subnetworks = false
  mtu                     = 1460
}

resource "google_compute_subnetwork" "subnet" {
  name                     = var.subnet_name
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_1_MIN"
    flow_sampling        = 0.1
    metadata             = "INCLUDE_ALL_METADATA"
  }

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

locals {
  subnet_iam_member_map = {
    for m in var.iam_members :
    "${m.role}|${m.member}" => m
  }
}

resource "google_compute_subnetwork_iam_member" "members" {
  for_each   = local.subnet_iam_member_map
  project    = google_compute_subnetwork.subnet.project
  region     = google_compute_subnetwork.subnet.region
  subnetwork = google_compute_subnetwork.subnet.name
  role       = each.value.role
  member     = each.value.member
}

resource "google_compute_address" "static_internal_ip" {
  name         = "static-internal-ip"
  subnetwork   = google_compute_subnetwork.subnet.id
  address_type = "INTERNAL"
  address      = var.internal_ip_address
  region       = var.region
  project      = var.project_id
  labels       = var.labels
}

resource "google_dns_managed_zone" "private_zone" {
  name        = "private-zone"
  dns_name    = "internal.${var.environment}."
  description = "Private DNS zone for internal services"
  labels      = var.labels

  visibility = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }
}

resource "google_dns_record_set" "qdrant_dns_record" {
  name         = "qdrant.internal.${var.environment}."
  managed_zone = google_dns_managed_zone.private_zone.name
  type         = "A"
  ttl          = 300

  rrdatas = [google_compute_address.static_internal_ip.address]
}

resource "google_compute_router" "router" {
  name    = "${var.network_name}-router"
  region  = var.region
  network = google_compute_network.vpc.id
  project = var.project_id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.network_name}-nat"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  project                            = var.project_id
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# PSA setup
resource "google_compute_global_address" "private_ip_alloc" {
  name          = "private-ip-alloc"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
  project       = var.project_id
  labels        = var.labels
}

resource "google_service_networking_connection" "default" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_alloc.name]
}

resource "google_compute_firewall" "allow_vertex_to_qdrant" {
  name    = "${var.network_name}-allow-vertex-to-qdrant"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["6333", "6334"]
  }

  source_ranges = ["${google_compute_global_address.private_ip_alloc.address}/${google_compute_global_address.private_ip_alloc.prefix_length}"]
}

# PSC NAT Subnet, required for publishing services via PSC
resource "google_compute_subnetwork" "psc_subnet" {
  count         = var.psc_subnet_cidr != null ? 1 : 0
  name          = "${var.network_name}-psc-subnet"
  ip_cidr_range = var.psc_subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project_id
  purpose       = "PRIVATE_SERVICE_CONNECT"
}

resource "google_service_account" "llm_sa" {
  project      = var.project_id
  account_id   = var.sa_name
  display_name = "LLM Cloud Run Service Account"
  description  = "Service account for running LLM on Cloud Run"
}

resource "google_project_iam_member" "llm_sa_roles" {
  for_each = toset([
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.llm_sa.email}"
}

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id    = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_name
  description   = "Docker repository for container images"

  cleanup_policies = [
    {
      id     = "delete-old-untagged"
      action = "DELETE"
      condition = {
        tag_state  = "UNTAGGED"
        older_than = "30d"
      }
    },
    {
      id     = "delete-old-tagged"
      action = "DELETE"
      condition = {
        tag_state  = "TAGGED"
        older_than = "90d"
      }
    }
  ]

  labels = merge(var.labels, { component = "artifact-registry" })

  iam_members = [
    {
      role   = "roles/artifactregistry.reader"
      member = "serviceAccount:${google_service_account.llm_sa.email}"
    }
  ]
}

module "cloud_storage" {
  source = "./modules/cloud_storage"

  name       = var.bucket_name
  project_id = var.project_id
  location   = var.region

  labels = merge(var.labels, { component = "gcs-bucket" })

  iam_members = [
    {
      role   = "roles/storage.objectUser"
      member = "serviceAccount:${google_service_account.llm_sa.email}"
    }
  ]
}

module "network" {
  source = "./modules/network"

  project_id          = var.project_id
  environment         = var.environment
  region              = var.region
  network_name        = var.network_name
  subnet_name         = var.subnet_name
  subnet_cidr         = var.subnet_cidr
  pods_cidr           = var.pods_cidr
  services_cidr       = var.services_cidr
  internal_ip_address = var.qdrant_internal_ip

  labels = merge(var.labels, { component = "vpc-network" })

  iam_members = [
    {
      role   = "roles/compute.networkUser"
      member = "serviceAccount:${google_service_account.llm_sa.email}"
    }
  ]
}

module "gke_cluster" {
  source = "./modules/gke"

  project_id          = var.project_id
  cluster_name        = var.gke_cluster_name
  location            = var.region
  network             = module.network.network_name
  subnetwork          = module.network.subnet_name
  pods_range_name     = module.network.pods_range_name
  services_range_name = module.network.services_range_name

  labels = merge(var.labels, { component = "gke-cluster" })
}

resource "kubernetes_namespace_v1" "vdb_namespace" {
  metadata {
    name = var.vector_db_namespace
  }
}

module "etl_workload_identity" {
  source = "./modules/workload_identity"

  project_id       = var.project_id
  gsa_name         = "etl-job-sa"
  gsa_display_name = "ETL Job Service Account"
  gsa_description  = "Service Account for BigQuery to vectordb ETL Job"
  roles = [
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/aiplatform.user",
  ]
  ksa_name  = "etl-job-sa"
  namespace = kubernetes_namespace_v1.vdb_namespace.metadata[0].name
}

module "qdrant_tls" {
  source = "./modules/self_signed_cert"

  common_name  = module.network.static_internal_ip
  organization = "Conversational Search"

  ip_addresses = [module.network.static_internal_ip]
  dns_names    = ["qdrant.internal.${var.environment}", "qdrant", "qdrant.${var.vector_db_namespace}.svc.cluster.local", "localhost"]

  validity_period_hours = 87600

  secret_name = "qdrant-tls-secret"
  namespace   = kubernetes_namespace_v1.vdb_namespace.metadata[0].name
}

module "secret_manager" {
  source = "./modules/secret_manager"

  project_id = var.project_id

  secrets = {
    "qdrant-ca-cert" = module.qdrant_tls.ca_cert_pem
    "qdrant-api-key" = var.qdrant_api_key
  }

  labels = merge(var.labels, { component = "secret-manager" })

  iam_members = []
}

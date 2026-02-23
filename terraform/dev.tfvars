# Project configuration
project_id  = "hm-contextual-search-f3d5"
region      = "europe-west1"
environment = "dev"

# Service accounts
sa_name = "llm-sa-dev"

# Artifact Registry
artifact_registry_name = "llm-ar-dev"

# GCS Bucket
bucket_name = "open-llms-dev"

# VPC Network
network_name       = "vectordb-vpc"
subnet_name        = "vectordb-subnet"
subnet_cidr        = "10.0.0.0/24"
pods_cidr          = "10.4.0.0/20"
services_cidr      = "10.8.0.0/24"
qdrant_internal_ip = "10.0.0.50" # make sure it is within subnet CIDR
psc_subnet_cidr    = "10.0.1.0/24"

# GKE Cluster
gke_cluster_name    = "vectordb-gke-cluster-dev"
vector_db_namespace = "qdrant"

# Labels
labels = {
  environment = "dev"
  managed-by  = "terraform"
}

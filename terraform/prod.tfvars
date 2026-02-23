# Project configuration
project_id  = ""
region      = "europe-west1"
environment = "prod"

# Service accounts
sa_name = "llm-sa-prod"

# Artifact Registry
artifact_registry_name = "llm-ar-prod"

# GCS Bucket
bucket_name = "open-llms-prod"

# VPC Network
network_name       = "vectordb-vpc"
subnet_name        = "vectordb-subnet"
subnet_cidr        = "10.0.0.0/24"
pods_cidr          = "10.4.0.0/20"
services_cidr      = "10.8.0.0/24"
qdrant_internal_ip = "10.0.0.50" # make sure it is within subnet CIDR
psc_subnet_cidr    = "10.0.1.0/24"

# GKE Cluster
gke_cluster_name    = "vectordb-gke-cluster-prod"
vector_db_namespace = "qdrant"

# Labels
labels = {
  environment = "prod"
  managed-by  = "terraform"
}

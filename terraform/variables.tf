variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "environment" {
  description = "The environment (dev, prod, etc.)"
  type        = string
}

variable "region" {
  description = "The GCP region for the Cloud Run service."
  type        = string
}

variable "sa_name" {
  description = "The name of the service account."
  type        = string
}

variable "artifact_registry_name" {
  description = "The name/ID of the Artifact Registry repository."
  type        = string
}

variable "bucket_name" {
  description = "The name of the GCS bucket."
  type        = string
}

variable "labels" {
  description = "Labels to apply to the resources."
  type        = map(string)
  default     = {}
}

variable "network_name" {
  description = "The name of the VPC network."
  type        = string
}

variable "subnet_name" {
  description = "The name of the VPC subnet."
  type        = string
}

variable "subnet_cidr" {
  description = "The CIDR range for the subnet (nodes)."
  type        = string
}

variable "pods_cidr" {
  description = "The CIDR range for pods."
  type        = string
}

variable "services_cidr" {
  description = "The CIDR range for services."
  type        = string
}

variable "qdrant_internal_ip" {
  description = "The specific internal IP address to reserve for Qdrant. If null, one will be automatically assigned."
  type        = string
  default     = null
}

variable "gke_cluster_name" {
  description = "The name of the GKE cluster."
  type        = string
}

variable "vector_db_namespace" {
  description = "The Kubernetes namespace for the vector database."
  type        = string
}

variable "qdrant_api_key" {
  description = "The API key for Qdrant."
  type        = string
  sensitive   = true
}

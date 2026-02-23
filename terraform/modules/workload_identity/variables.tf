variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gsa_name" {
  description = "Google Service Account Name"
  type        = string
}

variable "gsa_display_name" {
  description = "Google Service Account Display Name"
  type        = string
  default     = ""
}

variable "gsa_description" {
  description = "Google Service Account Description"
  type        = string
  default     = ""
}

variable "roles" {
  description = "List of IAM roles to assign to the service account"
  type        = list(string)
  default     = []
}

variable "ksa_name" {
  description = "Kubernetes Service Account Name"
  type        = string
}

variable "namespace" {
  description = "Kubernetes Namespace"
  type        = string
}

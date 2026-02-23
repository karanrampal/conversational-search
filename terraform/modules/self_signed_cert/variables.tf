variable "common_name" {
  description = "Common Name for the certificate"
  type        = string
}

variable "organization" {
  description = "Organization for the certificate"
  type        = string
}

variable "ip_addresses" {
  description = "List of IP addresses for the certificate"
  type        = list(string)
  default     = []
}

variable "dns_names" {
  description = "List of DNS names for the certificate"
  type        = list(string)
  default     = []
}

variable "validity_period_hours" {
  description = "Validity period in hours"
  type        = number
  default     = 8760
}

variable "secret_name" {
  description = "Name of the Kubernetes Secret"
  type        = string
}

variable "namespace" {
  description = "Kubernetes Namespace"
  type        = string
}

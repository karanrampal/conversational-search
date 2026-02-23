variable "project_id" {
  description = "The project ID."
  type        = string
}

variable "environment" {
  description = "The environment for the network resources."
  type        = string
}

variable "region" {
  description = "The region for the subnet."
  type        = string
}

variable "network_name" {
  description = "The name of the VPC network."
  type        = string
}

variable "subnet_name" {
  description = "The name of the subnet."
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

variable "iam_members" {
  description = "List of IAM role-member pairs to apply at subnet level (non-authoritative per member)."
  type = list(object({
    role   = string
    member = string
  }))
  default = []
}

variable "internal_ip_address" {
  description = "The specific internal IP address to reserve. If null, one will be automatically assigned."
  type        = string
  default     = null
}

variable "labels" {
  description = "Labels to apply to the network resources."
  type        = map(string)
  default     = {}
}

variable "psc_subnet_cidr" {
  description = "CIDR range for the Private Service Connect (PSC) NAT subnet. Required if exposing services via PSC."
  type        = string
  default     = null
}

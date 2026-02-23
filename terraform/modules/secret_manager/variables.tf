variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "secrets" {
  description = "A map of secrets to create, where the key is the secret ID and the value is the secret data."
  type        = map(string)
}

variable "labels" {
  description = "Labels to apply to the resources."
  type        = map(string)
  default     = {}
}

variable "iam_members" {
  description = "List of IAM role-member pairs to apply to the created secrets."
  type = list(object({
    role   = string
    member = string
  }))
  default = []
}

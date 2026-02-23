variable "project_id" {
  description = "The Google Cloud project ID"
  type        = string
}

variable "location" {
  description = "The location for the Artifact Registry repository"
  type        = string
}

variable "repository_id" {
  description = "The ID of the repository"
  type        = string
}

variable "description" {
  description = "Description of the repository"
  type        = string
  default     = "Docker repository"
}

variable "format" {
  description = "The format of the repository"
  type        = string
  default     = "DOCKER"
}

variable "cleanup_policies" {
  description = "List of cleanup policies for the repository"
  type = list(object({
    id     = string
    action = string
    condition = object({
      tag_state             = optional(string)
      older_than            = optional(string)
      newer_than            = optional(string)
      package_name_prefixes = optional(list(string))
    })
  }))
  default = [
    {
      id     = "delete-old-images"
      action = "DELETE"
      condition = {
        tag_state  = "UNTAGGED"
        older_than = "30d"
      }
    }
  ]
}

variable "labels" {
  description = "Default labels to apply to the repository"
  type        = map(string)
  default     = {}
}

variable "iam_members" {
  description = "List of IAM role-member pairs for the repository (stable composite keys used internally)."
  type = list(object({
    role   = string
    member = string
  }))
  default = []
}
variable "name" {
  description = "Bucket name (unique across GCS)."
  type        = string
}

variable "project_id" {
  description = "GCP project ID where the bucket should be created."
  type        = string
}

variable "location" {
  description = "Bucket location/region (e.g., europe-west1)."
  type        = string
}

variable "storage_class" {
  description = "Bucket storage class (STANDARD, NEARLINE, COLDLINE, ARCHIVE)."
  type        = string
  default     = "STANDARD"
}

variable "uniform_bucket_level_access" {
  description = "Enable uniform bucket-level access."
  type        = bool
  default     = true
}

variable "versioning" {
  description = "Enable object versioning on the bucket."
  type        = bool
  default     = false
}

variable "labels" {
  description = "Labels to apply to the bucket."
  type        = map(string)
  default     = {}
}

variable "iam_members" {
  description = "List of IAM role-member pairs to apply at bucket level (non-authoritative per member)."
  type = list(object({
    role   = string
    member = string
  }))
  default = []
}

variable "lifecycle_rules" {
  description = "Lifecycle rules for the bucket per google_storage_bucket.lifecycle_rule schema."
  type = list(object({
    action = object({
      type          = string
      storage_class = optional(string)
    })
    condition = object({
      age                        = optional(number)
      created_before             = optional(string)
      with_state                 = optional(string)
      num_newer_versions         = optional(number)
      matches_storage_class      = optional(list(string))
      noncurrent_time_before     = optional(string)
      days_since_noncurrent_time = optional(number)
    })
  }))
  default = []
}

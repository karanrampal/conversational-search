resource "google_storage_bucket" "bucket" {
  name                        = var.name
  project                     = var.project_id
  location                    = var.location
  storage_class               = var.storage_class
  labels                      = var.labels
  uniform_bucket_level_access = var.uniform_bucket_level_access

  versioning {
    enabled = var.versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      action {
        type          = lifecycle_rule.value.action.type
        storage_class = try(lifecycle_rule.value.action.storage_class, null)
      }
      condition {
        age                        = try(lifecycle_rule.value.condition.age, null)
        created_before             = try(lifecycle_rule.value.condition.created_before, null)
        with_state                 = try(lifecycle_rule.value.condition.with_state, null)
        num_newer_versions         = try(lifecycle_rule.value.condition.num_newer_versions, null)
        matches_storage_class      = try(lifecycle_rule.value.condition.matches_storage_class, null)
        noncurrent_time_before     = try(lifecycle_rule.value.condition.noncurrent_time_before, null)
        days_since_noncurrent_time = try(lifecycle_rule.value.condition.days_since_noncurrent_time, null)
      }
    }
  }
}

locals {
  bucket_iam_member_map = {
    for m in var.iam_members :
    "${m.role}|${m.member}" => m
  }
}

resource "google_storage_bucket_iam_member" "members" {
  for_each = local.bucket_iam_member_map
  bucket   = google_storage_bucket.bucket.name
  role     = each.value.role
  member   = each.value.member
}

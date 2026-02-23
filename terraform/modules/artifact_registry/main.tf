resource "google_artifact_registry_repository" "repository" {
  project       = var.project_id
  location      = var.location
  repository_id = var.repository_id
  description   = var.description
  format        = var.format

  dynamic "cleanup_policies" {
    for_each = var.cleanup_policies
    content {
      id     = cleanup_policies.value.id
      action = cleanup_policies.value.action

      condition {
        tag_state             = lookup(cleanup_policies.value.condition, "tag_state", null)
        older_than            = lookup(cleanup_policies.value.condition, "older_than", null)
        newer_than            = lookup(cleanup_policies.value.condition, "newer_than", null)
        package_name_prefixes = lookup(cleanup_policies.value.condition, "package_name_prefixes", null)
      }
    }
  }

  labels = var.labels
}

locals {
  iam_member_map = {
    for m in var.iam_members :
    "${m.role}|${m.member}" => m
  }
}

resource "google_artifact_registry_repository_iam_member" "members" {
  for_each = local.iam_member_map

  project    = var.project_id
  location   = google_artifact_registry_repository.repository.location
  repository = google_artifact_registry_repository.repository.name
  role       = each.value.role
  member     = each.value.member
}
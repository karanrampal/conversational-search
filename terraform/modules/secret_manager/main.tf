resource "google_secret_manager_secret" "secret" {
  for_each = var.secrets

  project   = var.project_id
  secret_id = each.key

  replication {
    auto {}
  }

  labels = var.labels
}

resource "google_secret_manager_secret_version" "secret_version" {
  for_each = var.secrets

  secret      = google_secret_manager_secret.secret[each.key].id
  secret_data = each.value
}

locals {
  secret_iam_members = flatten([
    for secret_key, _ in var.secrets : [
      for iam in var.iam_members : {
        secret_key = secret_key
        role       = iam.role
        member     = iam.member
      }
    ]
  ])
}

resource "google_secret_manager_secret_iam_member" "member" {
  for_each = {
    for item in local.secret_iam_members :
    "${item.secret_key}.${item.role}.${item.member}" => item
  }

  project   = var.project_id
  secret_id = google_secret_manager_secret.secret[each.value.secret_key].secret_id
  role      = each.value.role
  member    = each.value.member
}

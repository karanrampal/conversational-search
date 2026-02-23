resource "google_service_account" "sa" {
  project      = var.project_id
  account_id   = var.gsa_name
  display_name = var.gsa_display_name
  description  = var.gsa_description
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset(var.roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.sa.email}"
}

resource "kubernetes_service_account_v1" "ksa" {
  metadata {
    name      = var.ksa_name
    namespace = var.namespace
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.sa.email
    }
  }
}

resource "google_service_account_iam_member" "workload_identity_binding" {
  service_account_id = google_service_account.sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/${kubernetes_service_account_v1.ksa.metadata[0].name}]"
}

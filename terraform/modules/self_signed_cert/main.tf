resource "tls_private_key" "ca_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "ca_cert" {
  private_key_pem   = tls_private_key.ca_key.private_key_pem
  is_ca_certificate = true

  subject {
    common_name  = "${var.organization} CA"
    organization = var.organization
  }

  validity_period_hours = var.validity_period_hours

  allowed_uses = [
    "cert_signing",
    "crl_signing",
    "digital_signature",
  ]
}

resource "tls_private_key" "server_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_cert_request" "server_csr" {
  private_key_pem = tls_private_key.server_key.private_key_pem

  subject {
    common_name  = var.common_name
    organization = var.organization
  }

  ip_addresses = var.ip_addresses
  dns_names    = var.dns_names
}

resource "tls_locally_signed_cert" "server_cert" {
  cert_request_pem   = tls_cert_request.server_csr.cert_request_pem
  ca_private_key_pem = tls_private_key.ca_key.private_key_pem
  ca_cert_pem        = tls_self_signed_cert.ca_cert.cert_pem

  validity_period_hours = var.validity_period_hours

  allowed_uses = [
    "key_encipherment",
    "digital_signature",
    "server_auth",
  ]
}

resource "kubernetes_secret_v1" "tls_secret" {
  metadata {
    name      = var.secret_name
    namespace = var.namespace
  }

  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = tls_locally_signed_cert.server_cert.cert_pem
    "tls.key" = tls_private_key.server_key.private_key_pem
    "ca.pem"  = tls_self_signed_cert.ca_cert.cert_pem
  }
}

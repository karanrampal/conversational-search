output "secret_name" {
  value = kubernetes_secret_v1.tls_secret.metadata[0].name
}

output "ca_cert_pem" {
  value = tls_self_signed_cert.ca_cert.cert_pem
}

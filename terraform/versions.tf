terraform {
  required_version = ">= 1.13"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.8"
    }

    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.0"
    }

    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.1"
    }
  }

  backend "gcs" {
  }
}
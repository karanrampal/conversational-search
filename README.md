# Conversational Search

Repository for conversational search.

## Setup project

Run the following commands to setup your project:

- Setup gcloud using `gcloud init`, you may also need to run `gcloud auth login` and `gcloud auth application-default login`
- Setup infrastructure using terraform by running `make run-tf`. To destroy use `make run-tf ACTION=destroy`
- Setup artifact registry by running `gcloud auth configure-docker europe-west1-docker.pkg.dev`

## Setup GKE

To configure kubectl to fetch credentials and communicate with your new GKE cluster (only needs to be run once):
```
gcloud container clusters get-credentials <k8-cluster-name> --location europe-west1
```
For `<k8-cluster-name>` check `terraform/dev.tfvars` and use the value of `gke_cluster_name`.

## Install Qdrant

To create a new namespace in GKE (not necessary as now done in terraform):
```
kubectl create ns <namespace-name>
```
For `<namespace-name>` check `terraform/dev.tfvars` and use the value of `vector_db_namespace`.

If you want to create an api key for qdrant you can run the command:
```
openssl rand -base64 32
```
Copy its output to the environment variable `QDRANT_API_KEY` in the `.env` file and run `source .env`

To install qdrant do the following:

```
helm upgrade --install <release-name> manifests/qdrant-chart \
  --namespace qdrant \
  --set qdrant.apiKey=$QDRANT_API_KEY \
  --values manifests/qdrant-chart/values-<dev/prod>.yaml \
  --history-max 1 \
  --timeout 10m \
  --wait
```
`<release-name>` here can be qdrant or anything you like.

If you have made changes to the `manifests/qdrant-chart/Chart.yaml` file then you will have to first run `helm dependency update manifests/qdrant-chart`

**Note**: If you have made some changes to the wrapper helm chart and are getting forbidden updates error, you can run `helm uninstall <release-name> -n <namespace-name>` and then reinstall. This will delete your existing data in Qdrant and reinstall fresh.

## Local testing

Make sure the environment variable `QDRANT_API_KEY` is set, then run:
```
kubectl port-forward svc/qdrant <local-port>:6333 -n qdrant
```

Now you can test the qdrant connection using:
```
from qdrant_client import QdrantClient

client = QdrantClient(
    host="localhost",
    port=<local-port>,
    api_key=os.getenv("QDRANT_API_KEY"),
    https=False
)
```

## ETL job

Make sure the image `conversational-search` exists in the artifact registry, if not not run `make docker-bp`

To run the etl job:
```
helm upgrade --install <release-name> manifests/etl-job \
  --namespace qdrant \
  --values manifests/etl-job/values-<dev/prod>.yaml \
  --timeout 60m \
  --history-max 1 \
  --wait
```
`<release-name>` here can be etl or anything you like.

## Note

- To check if the helm charts are syntactically correct use:
```
helm lint <chart location 1> <chart location 2> ...
```

- To check logs of a job:
```
kubectl logs -n qdrant -l app=benchmark -f
```

- To get tls cert use:
```
kubectl get secret qdrant-tls-secret -n qdrant -o jsonpath='{.data.tls\.crt}' | base64 -d > qdrant_ca.crt
```

- To list running pods:
```
kubectl get pods -n qdrant
# you should see qdrant-0, qdrant-1 etc.
```

- Check pods disk contents:
```
kubectl exec -it -n qdrant qdrant-0 -- ls -la /qdrant/storage
```

- Check contents of collections
```
kubectl exec -it -n qdrant qdrant-0 -- ls -la /qdrant/storage/collections/articles_collection
```

- Create a `.env` file locally at root,
```
export GOOGLE_CLOUD_PROJECT="hm-contextual-search-f3d5"
export GOOGLE_CLOUD_LOCATION="europe-west1"
export GOOGLE_GENAI_USE_VERTEXAI=TRUE

export QDRANT_API_KEY="<qdrant api key>"
export TF_VAR_qdrant_api_key=${QDRANT_API_KEY}
```

## To Do

For PSC consumer add terraform code in the consumer,

1. Reserve an internal IP in THEIR subnet for the endpoint. This will be the IP their app uses to talk to Qdrant (e.g. 192.168.10.99)
```
resource "google_compute_address" "qdrant_endpoint_ip" {
  name         = "qdrant-psc-endpoint-ip"
  subnetwork   = google_compute_subnetwork.frontend_subnet.id
  address_type = "INTERNAL"
  region       = var.region
  project      = var.frontend_project_id
}
```

2. Create the PSC Forwarding Rule (The Tunnel)
```
resource "google_compute_forwarding_rule" "qdrant_psc_endpoint" {
  name    = "qdrant-psc-endpoint"
  region  = var.region
  project = var.frontend_project_id
  network = google_compute_network.frontend_vpc.id

  # Connects this local IP...
  ip_address = google_compute_address.qdrant_endpoint_ip.id
  
  # ...to YOUR Service Attachment
  target = "projects/hm-contextual-search-f3d5/regions/europe-west1/serviceAttachments/qdrant-psc-attachment"
  
  load_balancing_scheme = "" # Empty means it's a PSC Endpoint, not a Load Balancer
}
```

3. Create a DNS Record (Optional but recommended). Allows their code to use "qdrant.internal" instead of the raw IP
```
resource "google_dns_managed_zone" "private_zone" {
  name        = "private-zone"
  dns_name    = "internal."
  description = "Private DNS zone for internal services"
  
  visibility = "private"

  private_visibility_config {
    networks {
      network_url = module.network.network_id # You'll need to ensure network_id is outputted too, or use network_self_link
    }
  }
}

resource "google_dns_record_set" "qdrant_dns" {
  name         = "qdrant.internal."
  managed_zone = google_dns_managed_zone.private_zone.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_address.qdrant_endpoint_ip.address]
}
```

- change the image code or wherever the consumer is calling qdrant to,

```
from qdrant_client import QdrantClient

client = QdrantClient(url="http://qdrant.internal:6333", api_key=<read from secret manager>)
```
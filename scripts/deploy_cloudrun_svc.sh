#!/usr/bin/env bash
# Deploy a Cloud Run service with optional flags
set -euo pipefail

# Defaults (can be overridden via env or CLI args)
PROJECT_ID="${PROJECT_ID:-hm-contextual-search-f3d5}"
REGION="${REGION:-europe-west1}"
ENV="${ENV:-dev}"

IMAGE="${IMAGE:-us-docker.pkg.dev/cloudrun/container/gemma/gemma3-12b:latest}"

SERVICE_NAME="${SERVICE_NAME:-gemma3-12}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-llm-sa-${ENV}}"

CONCURRENCY="${CONCURRENCY:-4}"
CPU="${CPU:-8}"
MEMORY="${MEMORY:-32Gi}"
MIN_INSTANCES="${MIN_INSTANCES:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
TIMEOUT="${TIMEOUT:-3600}"
PORT="${PORT:-8080}"

# Startup Probe Defaults
# Start checking after 30s, check every 10s, allow up to 20 mins (120 * 10s) for model loading
SP_INIT_DELAY="${SP_INIT_DELAY:-30}"
SP_PERIOD_SECONDS="${SP_PERIOD_SECONDS:-10}"
SP_FAILURE_THRESHOLD="${SP_FAILURE_THRESHOLD:-120}"
SP_TIMEOUT_SECONDS="${SP_TIMEOUT_SECONDS:-10}"
SP_HEALTH_PATH="${SP_HEALTH_PATH:-/health}"

# Optional flags (set to empty to skip)
ENV_VARS="${ENV_VARS:-OLLAMA_NUM_PARALLEL=4}"   # comma-separated, e.g., --env-vars="MODEL_NAME=/models,VLLM_ARGS=--quantization bitsandbytes --load-format bitsandbytes --enforce-eager"

GPU="${GPU:-}"                                  # e.g., 1
CPU_THROTTLING="${CPU_THROTTLING:-false}"       # true/false → toggles cpu throttling

GCS_BUCKET="${GCS_BUCKET:-}"                    # Cloud Storage bucket name to mount
GCS_MOUNT_PATH="${GCS_MOUNT_PATH:-/models}"     # Mount path inside container
GCS_VOLUME_NAME="${GCS_VOLUME_NAME:-gcs-vol}"   # Volume name reference

VPC_NETWORK="${VPC_NETWORK:-vectordb-vpc}"      # VPC Network to connect to
VPC_SUBNET="${VPC_SUBNET:-vectordb-subnet}"     # VPC Subnet to connect to

# CLI overrides (simple parser: --key=value)
for arg in "$@"; do
  case $arg in
    --project=*) PROJECT_ID="${arg#*=}" ;;
    --region=*) REGION="${arg#*=}" ;;
    --service=*) SERVICE_NAME="${arg#*=}" ;;
    --image=*) IMAGE="${arg#*=}" ;;
    --env=*) ENV="${arg#*=}" ;;
    --service-account=*) SERVICE_ACCOUNT_NAME="${arg#*=}" ;;
    --concurrency=*) CONCURRENCY="${arg#*=}" ;;
    --vpc-network=*) VPC_NETWORK="${arg#*=}" ;;
    --vpc-subnet=*) VPC_SUBNET="${arg#*=}" ;;
    --cpu=*) CPU="${arg#*=}" ;;
    --memory=*) MEMORY="${arg#*=}" ;;
    --min-instances=*) MIN_INSTANCES="${arg#*=}" ;;
    --max-instances=*) MAX_INSTANCES="${arg#*=}" ;;
    --timeout=*) TIMEOUT="${arg#*=}" ;;
    --port=*) PORT="${arg#*=}" ;;
    --env-vars=*) ENV_VARS="${arg#*=}" ;;
    --gpu=*) GPU="${arg#*=}" ;;
    --cpu-throttling=*) CPU_THROTTLING="${arg#*=}" ;;
    --gcs-bucket=*) GCS_BUCKET="${arg#*=}" ;;
    --gcs-mount-path=*) GCS_MOUNT_PATH="${arg#*=}" ;;
    --gcs-volume-name=*) GCS_VOLUME_NAME="${arg#*=}" ;;
    --sp-init-delay=*) SP_INIT_DELAY="${arg#*=}" ;;
    --sp-failure-threshold=*) SP_FAILURE_THRESHOLD="${arg#*=}" ;;
    --sp-timeout-seconds=*) SP_TIMEOUT_SECONDS="${arg#*=}" ;;
    --sp-period-seconds=*) SP_PERIOD_SECONDS="${arg#*=}" ;;
    --sp-health-path=*) SP_HEALTH_PATH="${arg#*=}" ;;
    *) echo "Unknown arg: $arg" ;;
  esac
done

echo "=========================================="
echo "Cloud Run Deploy"
echo "Service: ${SERVICE_NAME}"
echo "Image:   ${IMAGE}"
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Env:     ${ENV}"
echo "Service Account: ${SERVICE_ACCOUNT_NAME}"
echo "=========================================="

# Build args array conditionally
ARGS=(
  "${SERVICE_NAME}"
  "--image" "${IMAGE}"
  "--region" "${REGION}"
  "--cpu" "${CPU}"
  "--memory" "${MEMORY}"
  "--min-instances" "${MIN_INSTANCES}"
  "--max-instances" "${MAX_INSTANCES}"
  "--timeout" "${TIMEOUT}"
  "--port" "${PORT}"
  "--service-account" "${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  "--labels" "env=${ENV}"
  "--no-allow-unauthenticated"
)

# Concurrency (skip if "default")
if [[ "${CONCURRENCY}" != "default" ]]; then
  ARGS+=("--concurrency" "${CONCURRENCY}")
fi

# Env vars
if [[ -n "${ENV_VARS}" ]]; then
  ARGS+=("--set-env-vars" "${ENV_VARS}")
fi

# Cloud Storage FUSE volume and mount
if [[ -n "${GCS_BUCKET}" ]]; then
  # Strip gs:// prefix if present
  CLEAN_PATH="${GCS_BUCKET#gs://}"
  # Strip trailing slash
  CLEAN_PATH="${CLEAN_PATH%/}"

  # Check if user provided a subfolder (e.g. bucket/folder)
  if [[ "$CLEAN_PATH" == *"/"* ]]; then
    BUCKET_NAME="${CLEAN_PATH%%/*}"
    SUBDIR="${CLEAN_PATH#*/}"
    # Use only-dir mount option to mount specific subfolder
    ARGS+=("--add-volume" "name=${GCS_VOLUME_NAME},type=cloud-storage,bucket=${BUCKET_NAME},mount-options=only-dir=${SUBDIR}")
  else
    ARGS+=("--add-volume" "name=${GCS_VOLUME_NAME},type=cloud-storage,bucket=${CLEAN_PATH}")
  fi

  ARGS+=("--add-volume-mount" "volume=${GCS_VOLUME_NAME},mount-path=${GCS_MOUNT_PATH}")
fi

# GPU flags
if [[ -n "${GPU}" ]]; then
  ARGS+=("--gpu" "${GPU}")
  ARGS+=("--gpu-type" "nvidia-l4")
  ARGS+=("--no-gpu-zonal-redundancy")
fi

# CPU throttling
if [[ "${CPU_THROTTLING}" == "true" ]]; then
  ARGS+=("--cpu-throttling")
else
  ARGS+=("--no-cpu-throttling")
fi

# Startup Probe
if [[ -n "${SP_INIT_DELAY}" ]]; then
  ARGS+=("--startup-probe" "httpGet.path=${SP_HEALTH_PATH},httpGet.port=${PORT},initialDelaySeconds=${SP_INIT_DELAY},failureThreshold=${SP_FAILURE_THRESHOLD},timeoutSeconds=${SP_TIMEOUT_SECONDS},periodSeconds=${SP_PERIOD_SECONDS}")
fi


# Direct VPC Egress
if [[ -n "${VPC_NETWORK}" && -n "${VPC_SUBNET}" ]]; then
  ARGS+=("--network" "${VPC_NETWORK}")
  ARGS+=("--subnet" "${VPC_SUBNET}")
  ARGS+=("--vpc-egress" "private-ranges-only")
fi

# Execute deploy
echo ""
echo "The following command will be executed:"
echo "gcloud run deploy ${ARGS[*]}"
echo ""
gcloud run deploy "${ARGS[@]}"

# Example command for reference:
# ./scripts/deploy_cloudrun_svc.sh --gpu=1 --service="gemma3-12-f" --image="europe-west1-docker.pkg.dev/hm-contextual-search-f3d5/llm-ar-dev/open-llms:latest" --gcs-bucket="gs://open-llms-dev/gemma3-12" --gcs-mount-path="/models" --port=8000 --concurrency="default" --env-vars="MODEL_NAME=/models,VLLM_ARGS=--quantization bitsandbytes --load-format bitsandbytes --enforce-eager"
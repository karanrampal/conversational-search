#!/usr/bin/env bash
# Manage Terraform deployments for the specified project and environment.
set -euo pipefail

# Configuration
PROJECT_ID="hm-contextual-search-f3d5"
REGION="europe-west1"
ENVIRONMENT="dev"
TF_STATE_BUCKET="tf-state-${PROJECT_ID}-${ENVIRONMENT}"
TF_LOCK_TIMEOUT="10m"

# Load .env file if it exists
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Parse command line arguments and set destroy flag early
ACTION="${1:-apply}"
DESTROY_FLAG=""
if [[ "${ACTION}" == "destroy" ]]; then
  DESTROY_FLAG="-destroy"
fi

# Validate action
if [[ "${ACTION}" != "apply" && "${ACTION}" != "destroy" ]]; then
  echo "Error: Invalid action '${ACTION}'"
  echo "Usage: $0 [apply|destroy]"
  echo "  apply   - Create or update resources (default)"
  echo "  destroy - Destroy all resources"
  exit 1
fi

echo "=========================================="
echo "Terraform ${ACTION^} Script"
echo "=========================================="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "State Bucket: gs://${TF_STATE_BUCKET}"
echo "Action: ${ACTION}"
echo "=========================================="
echo ""

echo "Step 1: Checking/Creating Terraform state bucket..."
if ! gsutil ls -p ${PROJECT_ID} gs://${TF_STATE_BUCKET} &> /dev/null
then
  echo "Creating Terraform state bucket gs://${TF_STATE_BUCKET}..."
  gsutil mb --pap enforced -b on -p ${PROJECT_ID} -l ${REGION} gs://${TF_STATE_BUCKET}
  sleep 10
  echo "✓ State bucket created"
else
  echo "✓ TF-state bucket gs://${TF_STATE_BUCKET} already exists"
fi
echo ""

echo "Step 2: Running terraform fmt..."
terraform -chdir=terraform fmt -check -recursive -diff
echo "✓ Formatting check passed"
echo ""

echo "Step 3: Initializing Terraform..."
terraform -chdir=terraform init -backend-config="bucket=${TF_STATE_BUCKET}"
echo "✓ Terraform initialized"
echo ""

echo "Step 4: Validating Terraform configuration..."
terraform -chdir=terraform validate
echo "✓ Configuration valid"
echo ""

echo "Step 5: Planning Terraform changes..."
terraform -chdir=terraform plan \
  ${DESTROY_FLAG} \
  -lock-timeout=${TF_LOCK_TIMEOUT} \
  -var-file=${ENVIRONMENT}.tfvars \
  -input=false \
  -compact-warnings \
  -out=plan.tfplan
echo "✓ Plan created"
echo ""

echo "Step 6: Applying Terraform changes..."
terraform -chdir=terraform apply \
  -auto-approve \
  -lock-timeout=${TF_LOCK_TIMEOUT} \
  -input=false \
  -compact-warnings \
  plan.tfplan
echo "✓ Action completed"
echo ""

# Show outputs only for apply
if [[ "${ACTION}" == "apply" ]]; then
  echo "=========================================="
  echo "Terraform Outputs:"
  echo "=========================================="
  terraform -chdir=terraform output
  echo ""
fi

echo "=========================================="
echo "Terraform ${ACTION^} completed."
echo "=========================================="
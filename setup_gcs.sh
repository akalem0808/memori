#!/bin/bash
# Script to set up Google Cloud Storage for Memori

# Default values
PROJECT_NAME="memori-project"
BUCKET_NAME="memori-storage"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="memori-service-account"

echo "=== Memori GCS Setup ==="
echo "This script will help you set up Google Cloud Storage for your Memori project."
echo

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: Google Cloud SDK (gcloud) is not installed."
    echo "Please install it first: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Ask for project name
read -p "Enter GCP project name (default: $PROJECT_NAME): " input
PROJECT_NAME=${input:-$PROJECT_NAME}

# Ask for bucket name
read -p "Enter GCS bucket name (default: $BUCKET_NAME): " input
BUCKET_NAME=${input:-$BUCKET_NAME}

# Ask for region
read -p "Enter region (default: $REGION): " input
REGION=${input:-$REGION}

# Ask for service account name
read -p "Enter service account name (default: $SERVICE_ACCOUNT_NAME): " input
SERVICE_ACCOUNT_NAME=${input:-$SERVICE_ACCOUNT_NAME}

echo
echo "Setting up with the following configuration:"
echo "Project: $PROJECT_NAME"
echo "Bucket: $BUCKET_NAME"
echo "Region: $REGION"
echo "Service Account: $SERVICE_ACCOUNT_NAME"
echo

read -p "Continue? (y/n): " confirm
if [[ $confirm != "y" && $confirm != "Y" ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo "=== Creating/configuring GCP project ==="
# Check if project exists
PROJECT_EXISTS=$(gcloud projects list --filter="PROJECT_ID=$PROJECT_NAME" --format="value(PROJECT_ID)")
if [ -z "$PROJECT_EXISTS" ]; then
    echo "Creating new project: $PROJECT_NAME"
    gcloud projects create $PROJECT_NAME --name="Memori App"
else
    echo "Project $PROJECT_NAME already exists."
fi

# Set as default project
gcloud config set project $PROJECT_NAME

# Enable required APIs
echo "Enabling necessary GCP APIs..."
gcloud services enable storage.googleapis.com

echo "=== Setting up GCS bucket ==="
# Check if bucket exists
BUCKET_EXISTS=$(gcloud storage ls gs://$BUCKET_NAME 2>&1 | grep -v "NotFound")
if [ -z "$BUCKET_EXISTS" ]; then
    echo "Creating storage bucket: $BUCKET_NAME in $REGION"
    gcloud storage buckets create gs://$BUCKET_NAME --location=$REGION
else
    echo "Bucket gs://$BUCKET_NAME already exists."
fi

echo "=== Creating service account ==="
# Create service account
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_NAME.iam.gserviceaccount.com"
SERVICE_ACCOUNT_EXISTS=$(gcloud iam service-accounts list --filter="email=$SERVICE_ACCOUNT_EMAIL" --format="value(email)")
if [ -z "$SERVICE_ACCOUNT_EXISTS" ]; then
    echo "Creating service account: $SERVICE_ACCOUNT_NAME"
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME --display-name="Memori Service Account"
else
    echo "Service account $SERVICE_ACCOUNT_EMAIL already exists."
fi

# Grant permissions
echo "Granting Storage Object Admin role to service account..."
gcloud projects add-iam-policy-binding $PROJECT_NAME \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.objectAdmin"

# Create and download key
echo "Creating service account key..."
KEY_FILE="$SERVICE_ACCOUNT_NAME-key.json"
gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account=$SERVICE_ACCOUNT_EMAIL

echo
echo "=== Setup Complete ==="
echo "Your GCS bucket has been set up at: gs://$BUCKET_NAME"
echo "Service account key saved to: $KEY_FILE"
echo 
echo "To use this configuration, set these environment variables:"
echo "export GCS_BUCKET_NAME=$BUCKET_NAME"
echo "export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/$KEY_FILE"
echo
echo "You can add these lines to your .env file:"
echo "GCS_BUCKET_NAME=$BUCKET_NAME"
echo "GOOGLE_APPLICATION_CREDENTIALS=$KEY_FILE"

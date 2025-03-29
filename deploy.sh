#!/bin/bash

# Define variables
SERVICE_NAME=<Your Service Name>
PROJECT_ID=<Your project ID>
REGION=<Your Region>
REPO_NAME="${SERVICE_NAME}"
IMAGE_NAME="us-central1-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME"


# Build the Docker image
echo "Building Docker image..."
docker build -t $SERVICE_NAME .

# Tag the Docker image
echo "Tagging Docker image..."
docker tag $SERVICE_NAME $IMAGE_NAME

# Push the Docker image to Artifact Registry
echo "Pushing Docker image to Artifact Registry..."
docker push $IMAGE_NAME

# Deploy the service to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID

echo "Deployment completed successfully!"

gcloud builds submit ./backend \
  --config=./backend/cloudbuild.yaml \
  --substitutions=_IMAGE=europe-north1-docker.pkg.dev/therecode-ai/therecode-backend/therecode-backend-api:v1
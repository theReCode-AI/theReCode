# gcloud builds submit ./frontend \
#   --config=./frontend/cloudbuild.yaml \
#   --substitutions=_IMAGE=europe-north1-docker.pkg.dev/todo-app-506706/harpic-cursor-v1/harpic-frontend:v3,_VITE_API_BASE_URL=https://harpic-cursor-v1-img-349908796899.europe-west1.run.app/api/v1

# gcloud run deploy harpic-frontend \
#   --image europe-north1-docker.pkg.dev/todo-app-506706/harpic-cursor-v1/harpic-frontend:v3 \
#   --region europe-north1 \
#   --port 8080 \
#   --allow-unauthenticated


# gcloud artifacts repositories create harpic-cursor-frontend-v1 --repository-format=docker --location=europe-north1 --description="FAST API APP TEST" --immutable-tags --async

# gcloud auth configure-docker europe-north1-docker.pkg.dev


# gcloud builds submit ./../frontend --tag europe-north1-docker.pkg.dev/todo-app-506706/harpic-cursor-frontend-v1/harpic-cursor-frontend-image-v1:frontend-v1tag

# gcloud builds submit ./frontend \
#   --tag europe-north1-docker.pkg.dev/todo-app-506706/harpic-cursor-frontend-v1/frontendimg-v1:frontend-v1tag \
#   --build-arg VITE_API_BASE_URL=https://harpic-cursor-v1-img-349908796899.europe-west1.run.app/api/v1

gcloud builds submit ./frontend \
  --config=./frontend/cloudbuild.yaml \
  --substitutions=_IMAGE=europe-north1-docker.pkg.dev/therecode-ai/therecode-agent-v1/harpic-frontend:v3,_VITE_API_BASE_URL=https://harpic-cursor-v1-img-349908796899.europe-west1.run.app/api/v1

gcloud run deploy harpic-frontend \
  --image europe-north1-docker.pkg.dev/therecode-ai/harpic-cursor-v1/harpic-frontend:v3 \
  --region europe-north1 \
  --port 8080 \
  --allow-unauthenticated


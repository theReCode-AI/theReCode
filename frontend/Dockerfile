FROM node:22-alpine AS builder

WORKDIR /app

ARG VITE_API_BASE_URL=/api/v1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine AS runtime

# Cloud Run sets PORT (often 8080; use whatever is injected).
ENV PORT=8080

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

# ---------- Stage 1: build the React/Vite bundle ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Browser calls go to the same origin (/api/...) and nginx proxies them to the
# backend Service, so no CORS and no hardcoded backend host in the bundle.
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# vite.config.ts uses base '/mystore_fastapi/' for GitHub Pages; in Kubernetes
# the site is served from the root.
RUN npm run build -- --base=/

# ---------- Stage 2: serve static files with nginx ----------
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

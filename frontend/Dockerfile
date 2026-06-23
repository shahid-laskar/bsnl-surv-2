# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies first (cache layer)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copy source
COPY frontend/ .

# Build — Vite outputs to /app/dist
ARG VITE_API_URL=http://localhost
ENV VITE_API_URL=$VITE_API_URL
ARG VITE_WS_URL=ws://localhost
ENV VITE_WS_URL=$VITE_WS_URL
RUN npm run build

# Production stage — serve static files with nginx
FROM nginx:1.27-alpine AS runner

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our SPA-friendly nginx config
COPY infra/nginx/spa.conf /etc/nginx/conf.d/default.conf

# Copy Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/index.html || exit 1

CMD ["nginx", "-g", "daemon off;"]

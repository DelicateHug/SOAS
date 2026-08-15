FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Production stage: nginx serving the built SPA over HTTPS, requiring a client cert
# from the proxy (the only peer that talks to the frontend container). The frontend
# is just static assets — we still mTLS it for consistency and to keep the proxy as
# the single ingress into the network.
FROM nginx:1.27-alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
# Certificates are mounted by docker-compose at /run/mtls.

# Placewise web (Next.js).
#   dev  (default for docker-compose.yml): next dev with the source bind-mounted, hot reload
#   prod (docker-compose.public.yml):      next build + next start, no source mount, no dev overlay
FROM node:22-alpine AS deps
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM deps AS prod
# Rewrites (/api/* → the api container) are resolved at build time, so the API URL is a build arg.
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL} NODE_ENV=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]

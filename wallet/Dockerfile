FROM node:25-bookworm-slim@sha256:81db02c4b671288a03915da9534dbd54f96d0e7c24d80ccc54f5b36b2e684370 AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY scripts/patch-jayson-stream-json.mjs scripts/patch-jayson-stream-json.mjs
RUN npm ci --ignore-scripts && node scripts/patch-jayson-stream-json.mjs
COPY tsconfig.json ./
COPY src ./src
RUN npx tsc -p tsconfig.json

FROM node:25-bookworm-slim@sha256:81db02c4b671288a03915da9534dbd54f96d0e7c24d80ccc54f5b36b2e684370
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
COPY scripts/patch-jayson-stream-json.mjs scripts/patch-jayson-stream-json.mjs
RUN npm ci --omit=dev --ignore-scripts && node scripts/patch-jayson-stream-json.mjs
COPY --from=build /app/dist ./dist
USER node
EXPOSE 8080
CMD ["node", "dist/src/resolver-server.js"]

FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_SITE_URL=https://leadscan.net
ARG API_INTERNAL_URL=http://api:8000
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL API_INTERNAL_URL=$API_INTERNAL_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
# Trang /tuyen-dung render phía máy chủ và gọi thẳng FastAPI lúc chạy → cần API_INTERNAL_URL ở cả image chạy
ARG API_INTERNAL_URL=http://api:8000
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0 API_INTERNAL_URL=$API_INTERNAL_URL
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
# Bản standalone không tự kèm public/ (logo, file brand) → copy riêng
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]

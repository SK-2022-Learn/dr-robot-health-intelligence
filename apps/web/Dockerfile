FROM node:24-alpine AS dependencies

WORKDIR /workspace/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:24-alpine AS builder

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
WORKDIR /workspace/apps/web
COPY --from=dependencies /workspace/apps/web/node_modules ./node_modules
COPY apps/web ./
RUN npm run build

FROM node:24-alpine AS runtime

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -S drrobot && adduser -S drrobot -G drrobot
WORKDIR /app
COPY --from=builder --chown=drrobot:drrobot /workspace/apps/web/.next/standalone ./
COPY --from=builder --chown=drrobot:drrobot /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=drrobot:drrobot /workspace/apps/web/public ./apps/web/public

USER drrobot
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

WORKDIR /app/apps/web
CMD ["node", "server.js"]

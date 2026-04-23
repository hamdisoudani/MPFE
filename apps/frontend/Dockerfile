# syntax=docker/dockerfile:1.7
FROM node:20-alpine AS base
RUN apk add --no-cache libc6-compat
WORKDIR /app

# ---- Build-time args (Railway injects these as --build-arg from service vars) ----
# NEXT_PUBLIC_* must be present at build time because Next.js inlines them into the client bundle.
ARG NEXT_PUBLIC_LANGGRAPH_API_URL
ARG NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY

# ---- Promote build args to ENV so `next build` and the runtime both see them ----
ENV NEXT_PUBLIC_LANGGRAPH_API_URL=${NEXT_PUBLIC_LANGGRAPH_API_URL} \
    NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID=${NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID} \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY}

FROM base AS deps
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN \
  if [ -f pnpm-lock.yaml ]; then corepack enable && pnpm i --frozen-lockfile; \
  elif [ -f yarn.lock ]; then corepack enable && yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  else npm install; fi

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

# Re-declare so the runner stage also sees them at runtime (Railway re-injects at run).
ARG NEXT_PUBLIC_LANGGRAPH_API_URL
ARG NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_LANGGRAPH_API_URL=${NEXT_PUBLIC_LANGGRAPH_API_URL} \
    NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID=${NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID} \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY}

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]

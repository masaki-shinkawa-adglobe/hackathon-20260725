FROM node:24-slim

WORKDIR /workspace

RUN corepack enable \
    && corepack prepare pnpm@11.16.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web apps/web

EXPOSE 3000

CMD ["pnpm", "--filter", "web", "dev", "--hostname", "0.0.0.0"]

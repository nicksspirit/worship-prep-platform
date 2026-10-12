# =============================================================================
# Build targets:
#   - local: Development container with hot-reload
#   - prod:  Production-optimized container (Cloud Run)
#   - ingress: Official Nginx container for the API HTTP/2 ingress
#   - test:  Test runner container
# =============================================================================

ARG UV_VERSION=0.10.12

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:3.13-slim-bookworm AS build

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /code

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.13 \
    UV_PROJECT_ENVIRONMENT=/venv

FROM build AS build-local

COPY uv.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --group local --frozen

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group local --locked

FROM build AS build-prod

COPY uv.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev --group prod --frozen

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --group prod --locked

FROM build AS build-test

COPY uv.lock pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --group test --frozen

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group test --locked

FROM node:22-slim AS node-deps

WORKDIR /code

COPY package.json package-lock.json ./
COPY patches/ ./patches/
RUN npm ci --legacy-peer-deps

FROM python:3.13-slim-bookworm AS runtime-base

SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/code/ \
    DJANGO_SETTINGS_MODULE="backend.settings" \
    PATH="/venv/bin:$PATH"

RUN groupadd -r rccgcm --gid 1000 \
    && useradd --no-log-init -r --uid 1000 -m -g rccgcm wpp \
    && mkdir -p /code /venv /code/public/media /code/public/static \
    && chown -R wpp:rccgcm /code /venv

WORKDIR /code

FROM runtime-base AS local

EXPOSE 8000

ENV DJANGO_ENV="local"

RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends sudo curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'wpp ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

COPY --from=build-local --chown=wpp:rccgcm /venv /venv
COPY --from=node-deps --chown=wpp:rccgcm /code/node_modules /code/node_modules
COPY --chown=wpp:rccgcm . /code/

USER wpp:rccgcm

RUN python -V && python -c "import django; print(f'Django {django.VERSION}')"

CMD ["/bin/bash", "/code/deploy/start-local.sh"]

FROM runtime-base AS prod

ARG SUPABASE_STORAGE_BUCKET=""
ARG SUPABASE_CATALOG_IMPORT_BUCKET=""
ARG SUPABASE_S3_ENDPOINT=""
ARG SUPABASE_S3_ACCESS_KEY=""
ARG SUPABASE_S3_SECRET_KEY=""
ARG SUPABASE_S3_REGION="us-east-1"

EXPOSE 8080

ENV DJANGO_ENV="prod" \
    DEBUG="False" \
    SUPABASE_STORAGE_BUCKET="${SUPABASE_STORAGE_BUCKET}" \
    SUPABASE_CATALOG_IMPORT_BUCKET="${SUPABASE_CATALOG_IMPORT_BUCKET}" \
    SUPABASE_S3_ENDPOINT="${SUPABASE_S3_ENDPOINT}" \
    SUPABASE_S3_ACCESS_KEY="${SUPABASE_S3_ACCESS_KEY}" \
    SUPABASE_S3_SECRET_KEY="${SUPABASE_S3_SECRET_KEY}" \
    SUPABASE_S3_REGION="${SUPABASE_S3_REGION}"

COPY --from=build-prod --chown=wpp:rccgcm /venv /venv
COPY --from=node-deps --chown=wpp:rccgcm /code/node_modules /code/node_modules
COPY --chown=wpp:rccgcm . /code/

USER wpp:rccgcm

RUN python -V && python -c "import django; print(f'Django {django.VERSION}')"

RUN python -c "from pathlib import Path; import django; Path('node_modules/_reactivated').mkdir(parents=True, exist_ok=True); django.setup(); from reactivated.apps import generate_schema; generate_schema(skip_cache=True)"

RUN npm exec build.client

RUN python manage.py collectstatic --noinput

CMD ["/bin/bash", "/code/deploy/start-django.sh"]

FROM nginx:1.30.5-trixie AS ingress

ENV PORT=8080 \
    GCP_PROJECT_ID="" \
    NGINX_ENVSUBST_OUTPUT_DIR=/tmp \
    NGINX_ENVSUBST_FILTER="^(PORT|GCP_PROJECT_ID)$"

COPY deploy/nginx-bolt.conf.template /etc/nginx/templates/wpp-nginx.conf.template
COPY deploy/nginx-logging.conf.template /etc/nginx/templates/wpp-nginx-logging.conf.template
COPY deploy/start-ingress.sh /usr/local/bin/start-ingress.sh

USER nginx
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/bin/sh", "/usr/local/bin/start-ingress.sh"]
CMD []

FROM runtime-base AS test

ENV DJANGO_ENV="test"

COPY --from=build-test --chown=wpp:rccgcm /venv /venv
COPY --from=node-deps --chown=wpp:rccgcm /code/node_modules /code/node_modules
COPY --chown=wpp:rccgcm . /code/

USER wpp:rccgcm

RUN python -V

CMD ["pytest"]

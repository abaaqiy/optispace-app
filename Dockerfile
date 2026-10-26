FROM node:24-bookworm-slim AS frontend

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.14-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=false

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY --from=frontend /app/dist ./dist
COPY --chmod=755 scripts/start-production.sh ./start-production.sh

# collectstatic needs settings, but does not connect to a database. These values
# are deliberately disposable: real secrets are supplied only at runtime.
RUN DATABASE_URL='postgresql://build:build@127.0.0.1:5432/build?sslmode=require' \
    DJANGO_DEBUG=false \
    DJANGO_SECRET_KEY='build-only-disposable-key-3fb82668c29d4ef5a17eb894027575620a9799ce' \
    DJANGO_ALLOWED_HOSTS=localhost \
    python backend/manage.py collectstatic --noinput

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin optispace \
    && chown -R optispace:optispace /app
USER optispace

EXPOSE 10000
CMD ["/app/start-production.sh"]

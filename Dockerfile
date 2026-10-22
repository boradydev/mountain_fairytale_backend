# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:a881a81282cca8c57f97014867fa651def1b3799030cc6b1cff45ed55ba8ef36
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1
WORKDIR /app
RUN pip install --no-cache-dir poetry==2.5.1
COPY pyproject.toml poetry.lock README.md ./
RUN poetry check --lock && poetry install --only main --no-root --no-ansi

FROM builder AS test
RUN poetry install --with dev --no-root --no-ansi
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY src ./src
COPY tests ./tests
COPY scripts ./scripts
CMD ["python", "-m", "pytest"]

FROM ${PYTHON_IMAGE} AS runtime
ARG VCS_REF=unknown
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_COMMIT_SHA=${VCS_REF}
LABEL org.opencontainers.image.title="Mountain Fairytale API" \
      org.opencontainers.image.revision=${VCS_REF}
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /data/geoapify && chown app:app /data/geoapify
COPY --from=builder /app/.venv ./.venv
COPY pyproject.toml ./
COPY src ./src
USER app
EXPOSE 8000
CMD ["python", "-m", "src.main"]

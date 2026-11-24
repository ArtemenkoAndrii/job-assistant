# Python patch version matches apps/jobfinder/.python-version (dev container and CI use it too).
# Runtime image for Job Finder: one image, two entry points (ADR-0005).
#   web:    uvicorn jobfinder.web.app:app --host 0.0.0.0 --port $PORT   (default command)
#   worker: python -m jobfinder.worker
FROM python:3.14.6-slim AS build

ARG UV_VERSION=0.13.9
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14.6-slim

RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=8080
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn jobfinder.web.app:app --host 0.0.0.0 --port ${PORT}"]

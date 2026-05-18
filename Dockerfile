# Build stage
FROM python:3.11-slim AS builder

WORKDIR /build
COPY . .
RUN pip install --no-cache-dir build && python -m build

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime deps
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl[server]

# Non-root user
RUN useradd --create-home ajp
USER ajp

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["ajp-server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]

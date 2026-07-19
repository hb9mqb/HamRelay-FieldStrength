# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/opt/py1812-runtime:/app/src \
    FIELD_STRENGTH_ARTIFACT_ROOT=/artifacts \
    FIELD_STRENGTH_DATABASE=/database/stations.sqlite3 \
    FIELD_STRENGTH_DEMO_ROOT=/app/demo \
    FIELD_STRENGTH_DEM_CACHE=/cache/dem \
    FIELD_STRENGTH_DEM_CATALOG=/app/config/dem-catalog.json \
    FIELD_STRENGTH_BASEMAP_CATALOG=/app/config/basemap-catalog.json \
    FIELD_STRENGTH_SEED_STATIONS=/app/examples/stations.json \
    ITU_AUTO_DOWNLOAD=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home /app app \
    && python -m venv /opt/venv

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY demo ./demo
COPY examples ./examples
COPY config ./config
RUN pip install --upgrade pip \
    && pip install . \
    && mkdir -p /opt/py1812-runtime \
    && cp -a /opt/venv/lib/python3.12/site-packages/Py1812 /opt/py1812-runtime/Py1812 \
    && mkdir -p /artifacts /data/dem /data/basemaps /cache/dem /database /config /itu \
    && chown -R app:app /opt/py1812-runtime /artifacts /cache /database /config

COPY docker/entrypoint.sh /usr/local/bin/field-strength-entrypoint
COPY docker/prepare_itu_maps.py /app/docker/prepare_itu_maps.py
RUN chmod 0755 /usr/local/bin/field-strength-entrypoint

USER app
EXPOSE 8765
VOLUME ["/artifacts", "/data/dem", "/data/basemaps", "/cache/dem", "/database", "/itu"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/v1/health', timeout=3).read()"

ENTRYPOINT ["field-strength-entrypoint"]
CMD ["uvicorn", "hamrelay_field_strength.service:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]

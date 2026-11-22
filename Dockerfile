FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt requirements.docker.txt ./
RUN python -m pip install -r requirements.docker.txt \
    && groupadd --gid 10001 simap \
    && useradd --uid 10001 --gid simap --no-create-home simap

COPY --chown=simap:simap . /app
RUN mkdir -p /app/media /app/staticfiles \
    && chown -R simap:simap /app/media /app/staticfiles \
    && sed -i 's/\r$//' /app/docker/entrypoint.sh \
    && cp /app/docker/entrypoint.sh /usr/local/bin/simap-entrypoint \
    && chmod 755 /usr/local/bin/simap-entrypoint

USER simap
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/simap-entrypoint"]
CMD ["web"]

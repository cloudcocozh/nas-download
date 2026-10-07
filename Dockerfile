FROM linuxserver/qbittorrent@sha256:b522f9f4b769f8f36d49d22d5eb6a92e9aa18904c6a1830b1439df511ec21983 AS engine
FROM python:3.11-slim
WORKDIR /app
COPY --from=engine /app/qbittorrent-nox /app/qbittorrent-nox
COPY --from=engine /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY server/requirements.txt /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir -r requirements.txt && useradd -u 1000 -m nasdownload
COPY server /app/server
COPY web /app/web
COPY deploy /app/deploy
USER 1000:1000
EXPOSE 7120
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:7120/api/v1/health',timeout=3))['ok']"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "deploy.entrypoint"]

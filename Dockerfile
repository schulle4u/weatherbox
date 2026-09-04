FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg espeak-ng tzdata \
    && rm -rf /var/lib/apt/lists/*

# Optional neural speech engine; voice models are mounted with the configuration.
ARG INSTALL_PIPER=false
RUN if [ "$INSTALL_PIPER" = "true" ]; then pip install 'piper-tts==1.7.0'; \
    elif [ "$INSTALL_PIPER" != "false" ]; then exit 1; fi

WORKDIR /opt/weatherbox
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install . \
    && groupadd --gid 10001 weatherbox \
    && useradd --uid 10001 --gid weatherbox --no-create-home --home-dir /var/lib/weatherbox weatherbox \
    && mkdir -p /etc/weatherbox /var/lib/weatherbox \
    && chown weatherbox:weatherbox /var/lib/weatherbox

USER 10001:10001
ENTRYPOINT ["wb-announcer", "--config", "/etc/weatherbox/config.yaml"]
CMD ["serve"]

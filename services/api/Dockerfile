FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d

ARG HERMES_COMMIT=e4ea0a0ed7fc24761b2b425146893561a73216e1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/api-venv/bin:/opt/hermes-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/var/lib/agentpulse

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates git passwd postgresql-client \
    && python -m pip install --no-cache-dir --upgrade setuptools==83.0.0 wheel==0.47.0 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/api-venv \
    && /opt/api-venv/bin/pip install --no-cache-dir --upgrade \
        pip==26.1.2 setuptools==83.0.0 wheel==0.47.0

WORKDIR /opt/agentpulse-api
COPY requirements.txt ./requirements.txt
RUN /opt/api-venv/bin/pip install --no-cache-dir -r requirements.txt

RUN git init /opt/hermes-agent \
    && git -C /opt/hermes-agent remote add origin https://github.com/NousResearch/hermes-agent.git \
    && git -C /opt/hermes-agent fetch --depth 1 origin "${HERMES_COMMIT}" \
    && git -C /opt/hermes-agent checkout --detach FETCH_HEAD \
    && sed -i \
        -e 's/cryptography==46\.0\.7/cryptography==48.0.1/g' \
        -e 's/Pillow==12\.2\.0/Pillow==12.3.0/g' \
        -e 's/mcp==1\.26\.0/mcp==1.28.1/g' \
        -e 's/starlette==1\.0\.1/starlette==1.3.1/g' \
        /opt/hermes-agent/pyproject.toml \
    && python -m venv /opt/hermes-venv \
    && /opt/hermes-venv/bin/pip install --no-cache-dir --upgrade \
        pip==26.1.2 setuptools==83.0.0 wheel==0.47.0 \
    && /opt/hermes-venv/bin/pip install --no-cache-dir "/opt/hermes-agent[acp,mcp]" \
    && /opt/hermes-venv/bin/pip check \
    && test "$(git -C /opt/hermes-agent rev-parse HEAD)" = "${HERMES_COMMIT}"

RUN useradd --uid 10001 --create-home --home-dir /var/lib/agentpulse agentpulse \
    && mkdir -p /srv/agentpulse /var/lib/agentpulse/work \
    && chown -R agentpulse:agentpulse /srv/agentpulse /var/lib/agentpulse \
    && chmod 0750 /var/lib/agentpulse /var/lib/agentpulse/work

WORKDIR /srv/agentpulse
COPY --chown=agentpulse:agentpulse app ./app

USER agentpulse
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

# Sandbox image for the Durable Banking Agent workshop.
# Bakes in: Python 3.12 + uv, Temporal CLI, modules 1-2, hackathon/ and
# solution/ (backend + frontend), mitmproxy + CA cert, and the network
# control panel.
#
# Build context is the repo root.
#
# The lab-start setup-workshop script stages /opt/workshop -> /root/workshop,
# starts background services, and bridges the real OPENAI_API_KEY secret.

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV WORKSPACE=/opt/workshop
ENV PYTHONUNBUFFERED=1

# ── 1. System packages ──────────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git procps \
    && rm -rf /var/lib/apt/lists/*

# ── 2. uv ────────────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── 3. Temporal CLI ──────────────────────────────────────────────────────────
RUN curl -sSf https://temporal.download/cli.sh | sh
ENV PATH="${PATH}:/root/.temporalio/bin"

# ── 4. Workshop source ───────────────────────────────────────────────────────
COPY modules/01-durable-bank-assistant/ /opt/workshop/modules/01-durable-bank-assistant/
COPY modules/02-durable-bank-tools/     /opt/workshop/modules/02-durable-bank-tools/
COPY hackathon/                        /opt/workshop/hackathon/
COPY solution/                         /opt/workshop/solution/

# ── 5. Python deps (exercise/ and solution/ each need their own venv) ───────
RUN for module in modules/01-durable-bank-assistant modules/02-durable-bank-tools; do \
        for variant in exercise solution; do \
            (cd "/opt/workshop/${module}/${variant}" && uv sync); \
        done; \
    done \
    && (cd /opt/workshop/hackathon/backend && uv sync) \
    && (cd /opt/workshop/solution/backend && uv sync)

# ── 6. mitmproxy + CA cert ───────────────────────────────────────────────────
RUN python3 -m venv /opt/mitmproxy-venv \
    && /opt/mitmproxy-venv/bin/pip install --upgrade pip \
    && /opt/mitmproxy-venv/bin/pip install mitmproxy flask \
    && ln -sf /opt/mitmproxy-venv/bin/mitmdump /usr/local/bin/mitmdump

# Generate the CA cert, trust it system-wide, and append it to every module's
# certifi bundle so proxied HTTPS calls through the workshop venvs succeed.
RUN mitmdump --listen-port 8889 --set block_global=false & \
    sleep 5 && kill %1 2>/dev/null || true; \
    cp /root/.mitmproxy/mitmproxy-ca-cert.pem \
       /usr/local/share/ca-certificates/mitmproxy-ca.crt \
    && update-ca-certificates \
    && MITM_CA=/root/.mitmproxy/mitmproxy-ca-cert.pem; \
    for module in modules/01-durable-bank-assistant modules/02-durable-bank-tools; do \
        for variant in exercise solution; do \
            bundle="/opt/workshop/${module}/${variant}/.venv/lib/python3.12/site-packages/certifi/cacert.pem"; \
            [ -f "$bundle" ] && cat "$MITM_CA" >> "$bundle" && echo "Patched certifi in ${module}/${variant}"; \
        done; \
    done; \
    for appdir in hackathon/backend solution/backend; do \
        bundle="/opt/workshop/${appdir}/.venv/lib/python3.12/site-packages/certifi/cacert.pem"; \
        [ -f "$bundle" ] && cat "$MITM_CA" >> "$bundle" && echo "Patched certifi in ${appdir}"; \
    done

# ── 7. Network control panel ─────────────────────────────────────────────────
RUN mkdir -p /opt/proxy/static
COPY instruqt/docker/proxy/toggle_addon.py /opt/proxy/toggle_addon.py
COPY instruqt/docker/proxy/controlpanel.py /opt/proxy/controlpanel.py
COPY instruqt/docker/proxy/state.json      /opt/proxy/state.json
COPY instruqt/docker/proxy/static/         /opt/proxy/static/

# Shared setup logic, called by both track_scripts/setup-workshop and every
# challenge's own setup-workshop. Instruqt's per-challenge Preview feature
# skips track-level scripts, so a challenge previewed standalone still needs
# to stage /root/workshop and start Temporal/mitmproxy/the control panel
# itself; the sentinel file inside the script makes repeat calls a no-op.
COPY instruqt/docker/bootstrap-workshop.sh /opt/bootstrap-workshop.sh
RUN chmod +x /opt/bootstrap-workshop.sh

# ── 8. Shell environment ─────────────────────────────────────────────────────
# These have to be Docker ENV, not appended to /etc/bash.bashrc: Debian's
# /etc/bash.bashrc starts with `[ -z "${PS1-}" ] && return`, so any
# non-interactive shell (every nohup'd process a lifecycle script starts)
# would source it, hit that guard, and never reach exports appended below it.
# ENV applies to every process unconditionally, interactive or not. (PATH
# already includes the Temporal CLI from step 3.)
ENV TEMPORAL_ADDRESS="127.0.0.1:7233"
ENV HTTP_PROXY="http://127.0.0.1:8888"
ENV HTTPS_PROXY="http://127.0.0.1:8888"
ENV NO_PROXY="127.0.0.1,localhost"
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

RUN echo '[ -f /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion' >> /etc/bash.bashrc

WORKDIR /root

# Keep PID 1 alive. Without a CMD, bash reads EOF on stdin with no TTY and
# exits immediately: the container dies with status 0 before the tab proxy
# can reach any port, every tab returns HTTP 572, and every lifecycle script
# still logs success because scripts do not go through the proxy.
CMD ["sleep", "infinity"]

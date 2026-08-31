# Sandbox image for the Durable Banking Agent workshop (Java edition).
# Bakes in: JDK 21 (Temurin) + Maven, Temporal CLI, modules 1-2, hackathon/ and
# solution/ (backend + frontend), mitmproxy + CA cert, and the network
# control panel.
#
# Build context is the repo root.
#
# The lab-start setup-workshop script stages /opt/workshop -> /root/workshop,
# starts background services, and bridges the real OPENAI_API_KEY secret.

FROM eclipse-temurin:21-jdk

ENV DEBIAN_FRONTEND=noninteractive
ENV WORKSPACE=/opt/workshop

# ── 1. System packages ──────────────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates git procps python3 python3-venv maven vim \
    && rm -rf /var/lib/apt/lists/*

# ── 2. Maven local repo warm-up moved to step 5 (needs source present) ──────

# ── 3. Temporal CLI ──────────────────────────────────────────────────────────
RUN curl -sSf https://temporal.download/cli.sh | sh
ENV PATH="${PATH}:/root/.temporalio/bin"

# ── 4. Workshop source ───────────────────────────────────────────────────────
# The frontends live at the repo root (shared with the Python track) while
# the Java backends live under java/. Main.java / ApiMain.java resolve their
# frontend via the relative path "../../../hackathon/frontend/index.html" (or
# "../../../solution/frontend/index.html"), so the on-disk layout must put
# backend/ and frontend/ as siblings under hackathon/ and solution/, exactly
# like the Python track - only backend/'s contents differ (Java, not Python).
COPY java/modules/01-durable-bank-assistant/ /opt/workshop/modules/01-durable-bank-assistant/
COPY java/modules/02-durable-bank-tools/     /opt/workshop/modules/02-durable-bank-tools/
COPY hackathon/frontend/                    /opt/workshop/hackathon/frontend/
COPY java/hackathon/backend/                /opt/workshop/hackathon/backend/
COPY solution/frontend/                     /opt/workshop/solution/frontend/
COPY java/solution/backend/                 /opt/workshop/solution/backend/

# ── 5. Maven deps (exercise/ and solution/ each need their own local repo warm-up) ──
RUN for module in modules/01-durable-bank-assistant modules/02-durable-bank-tools; do \
        for variant in exercise solution; do \
            (cd "/opt/workshop/${module}/${variant}" && mvn -q -B dependency:go-offline); \
        done; \
    done \
    && (cd /opt/workshop/hackathon/backend && mvn -q -B dependency:go-offline) \
    && (cd /opt/workshop/solution/backend && mvn -q -B dependency:go-offline)

# ── 6. mitmproxy + CA cert ───────────────────────────────────────────────────
RUN python3 -m venv /opt/mitmproxy-venv \
    && /opt/mitmproxy-venv/bin/pip install --upgrade pip \
    && /opt/mitmproxy-venv/bin/pip install mitmproxy flask \
    && ln -sf /opt/mitmproxy-venv/bin/mitmdump /usr/local/bin/mitmdump

# Generate the CA cert and trust it system-wide so proxied HTTPS calls from
# the JVM (which uses the system/JDK trust store, not a per-module bundle
# like Python's certifi) succeed.
RUN mitmdump --listen-port 8889 --set block_global=false & \
    sleep 5 && kill %1 2>/dev/null || true; \
    cp /root/.mitmproxy/mitmproxy-ca-cert.pem \
       /usr/local/share/ca-certificates/mitmproxy-ca.crt \
    && update-ca-certificates \
    && keytool -importcert -noprompt -trustcacerts \
       -alias mitmproxy-ca \
       -file /root/.mitmproxy/mitmproxy-ca-cert.pem \
       -keystore "${JAVA_HOME}/lib/security/cacerts" \
       -storepass changeit

# ── 7. Network control panel ─────────────────────────────────────────────────
RUN mkdir -p /opt/proxy/static
COPY instruqt/docker-java/proxy/toggle_addon.py /opt/proxy/toggle_addon.py
COPY instruqt/docker-java/proxy/controlpanel.py /opt/proxy/controlpanel.py
COPY instruqt/docker-java/proxy/state.json      /opt/proxy/state.json
COPY instruqt/docker-java/proxy/static/         /opt/proxy/static/

# Shared setup logic, called by both track_scripts/setup-workshop and every
# challenge's own setup-workshop. Instruqt's per-challenge Preview feature
# skips track-level scripts, so a challenge previewed standalone still needs
# to stage /root/workshop and start Temporal/mitmproxy/the control panel
# itself; the sentinel file inside the script makes repeat calls a no-op.
COPY instruqt/docker-java/bootstrap-workshop.sh /opt/bootstrap-workshop.sh
RUN chmod +x /opt/bootstrap-workshop.sh

# ── 8. Shell environment ─────────────────────────────────────────────────────
# TEMPORAL_ADDRESS/HTTP_PROXY/HTTPS_PROXY/etc are deliberately NOT Docker ENV:
# a container-wide ENV applies to every process, including Instruqt's own
# internal agent that backs terminal/code-editor tabs. Routing that agent's
# own authenticated calls through mitmproxy's TLS interception breaks its
# session, which surfaces as "Unauthorized" on the Editor/terminal tabs while
# type: service tabs (a plain external port-proxy, untouched by anything
# inside the container) keep working. Instead these get written to a
# dedicated /root/.workshop-env (bootstrap-workshop.sh does this, alongside
# OPENAI_API_KEY) - NOT appended to /root/.bashrc directly: Debian's default
# .bashrc starts with `[ -z "$PS1" ] && return`, so a non-interactive
# lifecycle script sourcing it would hit that guard and never reach an
# appended block. Every lifecycle script explicitly sources
# /root/.workshop-env before launching anything with nohup, so app processes
# still get these vars; .bashrc also sources this file (after its own
# early-return) purely for interactive terminal convenience. Instruqt's
# agent, which never sources either file, never sees them.
RUN echo '[ -f /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion' >> /etc/bash.bashrc

WORKDIR /root

# Keep PID 1 alive. Without a CMD, bash reads EOF on stdin with no TTY and
# exits immediately: the container dies with status 0 before the tab proxy
# can reach any port, every tab returns HTTP 572, and every lifecycle script
# still logs success because scripts do not go through the proxy.
CMD ["sleep", "infinity"]

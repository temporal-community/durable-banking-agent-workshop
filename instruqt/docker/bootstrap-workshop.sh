#!/bin/bash
# Shared bootstrap: stages the workshop tree and starts background services
# (mitmproxy, the network control panel, the Temporal dev server) and
# bridges the OPENAI_API_KEY secret into the attendee's shell.
#
# Baked into the image at /opt/bootstrap-workshop.sh and called from BOTH
# track_scripts/setup-workshop and every challenge's own setup-workshop.
# Instruqt's per-challenge "Preview" feature only runs that challenge's own
# lifecycle scripts, not the track-level ones, so a challenge previewed on
# its own would otherwise start with no /root/workshop, no Temporal server,
# and no proxy. Guarded by a sentinel file so re-running it (track setup,
# then a challenge's own setup) is a no-op after the first run.
set -euo pipefail

if [ -f /root/.workshop-bootstrapped ]; then
    exit 0
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY is not set. Configure the Instruqt secret before starting the track." >&2
    exit 1
fi

DIRS=(
    modules/01-durable-bank-assistant
    modules/02-durable-bank-tools
    hackathon
    solution
)

# 1. Stage the workshop into the attendee's writable copy.
mkdir -p /root/workshop
for dir in "${DIRS[@]}"; do
    mkdir -p "/root/workshop/$(dirname "${dir}")"
    cp -r "/opt/workshop/${dir}" "/root/workshop/${dir}"
done

# 2. Stage proxy state into a writable location.
mkdir -p /root/proxy/static
cp -r /opt/proxy/* /root/proxy/

# 3. Start background services.
nohup mitmdump \
    --listen-port 8888 \
    --set block_global=false \
    --set ssl_insecure=false \
    -s /root/proxy/toggle_addon.py \
    > /tmp/proxy.log 2>&1 &

nohup /opt/mitmproxy-venv/bin/python /root/proxy/controlpanel.py \
    > /tmp/controlpanel.log 2>&1 &

nohup temporal server start-dev \
    --ip 0.0.0.0 \
    --db-filename /root/temporal.db \
    --log-level warn \
    > /tmp/temporal-server.log 2>&1 &

# 4. Wait for Temporal health.
for i in $(seq 1 60); do
    if temporal operator cluster health --address 127.0.0.1:7233 >/dev/null 2>&1; then
        echo "Temporal server healthy."
        break
    fi
    sleep 1
done

# 5. Bridge the secret into the attendee's shell. Instruqt injects secrets
#    into lifecycle scripts only, so any worker/uvicorn process the attendee
#    starts from a terminal would not see it otherwise.
cat >> /root/.bashrc <<BASHRC
export OPENAI_API_KEY="${OPENAI_API_KEY}"
BASHRC

touch /root/.workshop-bootstrapped
echo "==> Workshop bootstrap complete."

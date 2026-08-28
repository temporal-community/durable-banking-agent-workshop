#!/bin/bash
# Shared bootstrap: stages the workshop tree, starts background services
# (mitmproxy, the network control panel, the Temporal dev server), and mints
# a learner-scoped LiteLLM key via the secret broker.
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

SECRET_BROKER_BASE_URL="${SECRET_BROKER_BASE_URL:-https://tmprl-dem-cld-secret-broker-429214323166-us-west-1.s3.us-west-1.amazonaws.com/secret-broker}"
SECRET_BROKER_VERSION="${SECRET_BROKER_VERSION:-main}"
LITELLM_KEY_DURATION="${LITELLM_KEY_DURATION:-1d}"
LITELLM_MAX_BUDGET="${LITELLM_MAX_BUDGET:-5}"
LITELLM_ENV_FILE="/root/.litellm-env"
LITELLM_PROXY_HOST="${LITELLM_PROXY_HOST:-litellm-instruqt.tmprl-demo.cloud}"

export INSTRUQT_BROKER_URL="${INSTRUQT_BROKER_URL:-https://litellm-broker-instruqt.tmprl-demo.cloud}"
export INSTRUQT_BROKER_KEY_ID="${INSTRUQT_BROKER_KEY_ID:-v1}"
export INSTRUQT_LITELLM_TRACK_ID="${INSTRUQT_LITELLM_TRACK_ID:-${INSTRUQT_TRACK_SLUG:-durable-banking-agent}}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o}"

DIRS=(
    modules/01-durable-bank-assistant
    modules/02-durable-bank-tools
    hackathon
    solution
)

patch_runtime_proxy_config() {
    local toggle_addon="/root/proxy/toggle_addon.py"
    local controlpanel="/root/proxy/controlpanel.py"
    local openai_pattern='^[[:space:]]*"openai"[[:space:]]*:[[:space:]]*\[[^]]*\][[:space:]]*,[[:space:]]*$'
    local matches

    case "${LITELLM_PROXY_HOST}" in
        "" | *[!A-Za-z0-9.-]*)
            echo "ERROR: Invalid LiteLLM proxy hostname: ${LITELLM_PROXY_HOST}" >&2
            exit 1
            ;;
    esac

    matches="$(grep -Ec "${openai_pattern}" "${toggle_addon}" || true)"
    if [ "${matches}" -ne 1 ]; then
        echo "ERROR: Expected exactly one OpenAI host list in ${toggle_addon}; found ${matches}." >&2
        exit 1
    fi

    sed -E -i \
        "s|^([[:space:]]*\"openai\"[[:space:]]*:[[:space:]]*)\[[^]]*\]([[:space:]]*,[[:space:]]*)$|\\1[\"api.openai.com\", \"${LITELLM_PROXY_HOST}\"]\\2|" \
        "${toggle_addon}"

    sed -i \
        's|"openai": "OpenAI  (api.openai.com)",|"openai": "OpenAI  (LiteLLM gateway)",|' \
        "${controlpanel}"
}

mint_litellm_token() {
    if [ -z "${TEMPORAL_LITELLM_BROKER_SECRET:-}" ]; then
        echo "ERROR: TEMPORAL_LITELLM_BROKER_SECRET is not set. Configure the Instruqt secret before starting the track." >&2
        exit 1
    fi

    local installer="/tmp/install-secret-broker.sh"

    curl --fail --silent --show-error --location \
        --retry 10 \
        --retry-all-errors \
        --retry-delay 2 \
        --retry-max-time 60 \
        --connect-timeout 10 \
        "${SECRET_BROKER_BASE_URL}/${SECRET_BROKER_VERSION}/install.sh" \
        --output "${installer}"

    SECRET_BROKER_BASE_URL="${SECRET_BROKER_BASE_URL}" \
    SECRET_BROKER_VERSION="${SECRET_BROKER_VERSION}" \
        sh "${installer}"

    export TEMPORAL_LITELLM_BROKER_SECRET
    secret-broker litellm \
        --duration="${LITELLM_KEY_DURATION}" \
        --budget="${LITELLM_MAX_BUDGET}"

    # Make the minted key available to the remainder of this lifecycle script too.
    # shellcheck disable=SC1090
    . "${LITELLM_ENV_FILE}"
}

# 1. Stage the workshop into the attendee's writable copy.
mkdir -p /root/workshop
for dir in "${DIRS[@]}"; do
    mkdir -p "/root/workshop/$(dirname "${dir}")"
    cp -r "/opt/workshop/${dir}" "/root/workshop/${dir}"
done

# 2. Stage proxy state into a writable location.
mkdir -p /root/proxy/static
cp -r /opt/proxy/* /root/proxy/

# 3. Patch the writable proxy config before mitmproxy loads it: real model calls now route
#    through the LiteLLM proxy, not directly to api.openai.com, so the "openai" toggle needs to
#    block that host too for the network-kill demo to still work.
patch_runtime_proxy_config

# 4. Start background services.
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

# 5. Wait for Temporal health.
for i in $(seq 1 60); do
    if temporal operator cluster health --address 127.0.0.1:7233 >/dev/null 2>&1; then
        echo "Temporal server healthy."
        break
    fi
    sleep 1
done

# 6. Mint a learner-scoped LiteLLM key and expose it as OpenAI-compatible env.
mint_litellm_token

# 7. Bridge the minted key and the proxy/Temporal env into the attendee's shell.
#    Written to a dedicated /root/.workshop-env file, NOT set as a container-wide
#    Docker ENV and NOT appended to /etc/bash.bashrc (which returns early for
#    non-interactive shells). A container-wide ENV would also reach Instruqt's
#    own internal agent process that backs the terminal/code-editor tabs -
#    routing ITS authenticated calls through mitmproxy's TLS interception
#    breaks its session ("Unauthorized" on those tabs).
#
#    This is deliberately NOT appended straight to /root/.bashrc: Debian's
#    default /root/.bashrc starts with `[ -z "$PS1" ] && return`, so sourcing
#    it from a non-interactive script (every lifecycle script - setup/solve -
#    and any nohup'd background process) hits that guard and returns before
#    ever reaching an appended block, silently skipping it. Every one of our
#    lifecycle scripts sources /root/.workshop-env directly (not .bashrc) so
#    app processes actually get these vars; .bashrc also sources this file
#    (guarded by -f, after its own early-return) purely for interactive
#    terminal tab convenience. Instruqt's agent, which never sources either
#    file, never sees them.
cat > /root/.workshop-env <<'WORKSHOPENV'
if [ -f /root/.litellm-env ]; then
    set -a
    . /root/.litellm-env
    set +a
fi
export TEMPORAL_ADDRESS="127.0.0.1:7233"
export HTTP_PROXY="http://127.0.0.1:8888"
export HTTPS_PROXY="http://127.0.0.1:8888"
export NO_PROXY="127.0.0.1,localhost"
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
WORKSHOPENV

cat >> /root/.bashrc <<'BASHRC'
[ -f /root/.workshop-env ] && . /root/.workshop-env
BASHRC

touch /root/.workshop-bootstrapped
echo "==> Workshop bootstrap complete."

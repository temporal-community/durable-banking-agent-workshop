"""
mitmproxy addon that reads /root/proxy/state.json and blocks or passes
outbound requests based on which service groups are toggled off.

State file format:
{
  "kill_all": false,
  "services": {
    "openai": true,
    "geoip": true
  }
}
A value of true means the service is ALLOWED through.
"""
import json
from mitmproxy import http

STATE_FILE = "/root/proxy/state.json"

SERVICE_HOSTS = {
    "openai": ["api.openai.com"],
    "geoip": ["ip-api.com"],
}

DEFAULT_STATE = {
    "kill_all": False,
    "services": {k: True for k in SERVICE_HOSTS},
}


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return DEFAULT_STATE


def request(flow: http.HTTPFlow) -> None:
    state = _load_state()
    host = flow.request.pretty_host

    if state.get("kill_all"):
        flow.response = http.Response.make(
            503, b"[Workshop proxy] All external services disabled.", {"Content-Type": "text/plain"}
        )
        return

    services = state.get("services", {})
    for key, hostnames in SERVICE_HOSTS.items():
        if not services.get(key, True):
            if any(h in host for h in hostnames):
                flow.response = http.Response.make(
                    503,
                    f"[Workshop proxy] Service '{key}' is currently disabled.".encode(),
                    {"Content-Type": "text/plain"},
                )
                return

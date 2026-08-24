---
slug: durable-banking-agent
id: 0wk095dad8nv
type: challenge
title: 'Module 3: Durable Banking Agent'
teaser: Ledger Bank's fraud check is fragile. Temporalize it without changing what
  it does.
notes:
- type: text
  contents: |-
    # A transfer just got flagged

    Ledger Bank runs a real fraud investigation on every transfer: geolocate
    the request, compare it against where the account transacted last, and
    decide whether the travel implied is possible.

    The decision is made by an agent, not an if/else. The backend making that
    decision has no retries, no idempotency, and no memory of a crash.
- type: text
  contents: |-
    # Your job

    Wrap the transfer in a Temporal workflow. Turn the geo-IP lookup, the
    fraud-check agent call, and the ledger update into activities. Change
    nothing a customer would notice.
tabs:
- id: akvr81yhw1gc
  title: Backend
  type: terminal
  hostname: workshop
  workdir: /root/workshop/hackathon/backend
- id: 64f3mooextj2
  title: Frontend
  type: service
  hostname: workshop
  path: /
  port: 8080
- id: yblr9woe1s6o
  title: Temporal UI
  type: service
  hostname: workshop
  path: /
  port: 8233
- id: s8zyj601rsv7
  title: Network Control Panel
  type: service
  hostname: workshop
  path: /
  port: 5000
- id: 6ynb9ae8ckyi
  title: Editor
  type: code
  hostname: workshop
  path: /root/workshop/hackathon
- id: zyfdlj0ynyju
  title: Solution
  type: code
  hostname: workshop
  path: /root/workshop/solution
difficulty: advanced
timelimit: 10800
enhanced_loading: null
---

# Durable Banking Agent

> [!NOTE]
> **Your tabs.**
> - [button label="Backend" background="#444CE7"](tab-0) is your terminal, opened in `hackathon/backend`. Run `uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload` here. The `--host 0.0.0.0` matters: uvicorn's default of `127.0.0.1` is invisible to the Frontend tab's proxy and shows up there as a 572.
> - [button label="Frontend" background="#444CE7"](tab-1) is the live transfer UI: two accounts, a transfer form, and an incident log.
> - [button label="Temporal UI" background="#444CE7"](tab-2) is the event history once you have a workflow.
> - [button label="Network Control Panel" background="#444CE7"](tab-3) turns OpenAI and the geolocation service off, on demand.
> - [button label="Editor" background="#444CE7"](tab-4) is `hackathon/`, the code you're changing.
> - [button label="Solution" background="#444CE7"](tab-5) is the finished reference, `solution/`. Read it if you're stuck, but don't just copy it in. The point is building it.

## The Incident

Ledger Bank has two accounts, A (New York, USD) and B (London, USD-equivalent for this workshop).
Someone is trying to move money out of one of them from a location it has never transacted from
before. Open the [button label="Frontend" background="#444CE7"](tab-1) tab, pick a **spoof
location** far from an account's usual city, and submit a transfer. Watch it get declined, and
watch the incident log record it.

Now do a normal transfer between the two home cities. It goes through.

## Why This Is Fragile

Everything so far ran inside `hackathon/backend/main.py`, synchronously, in one process:

1. Geolocate the request's IP via `ip-api.com`. No retry: a slow or dropped call is a 500.
2. Compute the distance and elapsed time since the account's last transaction, and hand those facts
   to a fraud-check `Agent`, which decides to approve or decline. Not an if/else, read
   `fraud_check.py`.
3. Update the ledger in memory, with no idempotency key and no transaction boundary.

Kill the backend process mid-transfer (`Ctrl-C` in the [button label="Backend"
background="#444CE7"](tab-0) terminal, or toggle a service off in the [button label="Network
Control Panel" background="#444CE7"](tab-3) mid-request) and there is no way to know if the debit
happened, the credit happened, both, or neither. Nothing recorded what was in flight.

## The Task

Temporalize `hackathon/backend/` without changing the product:

- Wrap the transfer in a Temporal workflow, started from the `POST /transfer` endpoint.
- Turn the geo-IP lookup, the fraud-check agent call, and the ledger update into `@activity.defn`
  activities. Build the fraud-check `Agent` inside the workflow with `activity_as_tool`-wrapped
  tools, the same pattern as modules 1 and 2, not a plain-Python `Agent` outside Temporal.
- Give the ledger-update activity an idempotency key (the workflow ID) so a resumed run can't
  double-credit.
- A genuine fraud decline is permanent: raise `ApplicationError(..., non_retryable=True)`. A flaky
  geo-IP timeout is transient: let Temporal's default retry policy handle it, don't catch and
  convert it.
- Add a `workflow.sleep(...)` before the risky call, the same pacing trick from modules 1-2's
  network-kill demo, so you get a guaranteed window to kill the worker mid-transfer instead of
  racing the LLM's response time.

`solution/` is the fully temporalized reference if you want to compare shapes: same idea, `POST
/transfer` starts a workflow and returns a workflow ID instead of blocking, and the frontend polls
for the result. `hackathon/` and `solution/` are not required to end up identical; they just have
to behave the same way from the outside. If you run `solution/backend` to compare against it, start
it the same way, with an explicit host and port: `cd solution/backend && uv run python -m worker`
in one terminal, then `uv run uvicorn main:app --host 0.0.0.0 --port 8000` in another. Don't add
`--reload` here: every transfer writes `ledger.json` inside this same directory, and `--reload`
would restart the server on every write.

If you want `check-workshop`'s automated checks to find your workflows, use the task queue
`banking-transfer-tq` and workflow IDs prefixed `transfer-`, the same convention `solution/`
uses. Not required. Without it, verify the checklist below by reading the Temporal UI yourself.

## Prove It

You're done when all four of these hold. There's no leaderboard here, this is a checklist, not a
score.

1. **Resume, not restart.** Start a transfer, kill the worker process
   (`pkill -9 -f "modules/hackathon\|hackathon/backend"` or however you've named it) during the
   `workflow.sleep` window, restart the worker, and confirm in the [button label="Temporal UI"
   background="#444CE7"](tab-2) tab that the same workflow ID resumes and finishes, with the
   ledger showing neither a duplicated nor a lost transfer.
2. **Fraud declines don't retry.** A spoofed impossible-travel transfer shows exactly one failed
   attempt in event history, not a retrying activity.
3. **Geo-IP failures do retry.** Toggle **Geolocation** off in the [button label="Network Control
   Panel" background="#444CE7"](tab-3) tab mid-transfer; the activity should show as **Retrying**,
   not failed.
4. **Idempotent ledger updates.** Re-delivering the same workflow ID's ledger-update activity (a
   replay, or a manual retry) does not move money twice.

Run `check-workshop`'s checks yourself at any time. Ask your facilitator how, or look for the
`check-workshop` script's own output for what it's able to verify automatically versus what you
should confirm by hand.

## Stretch Goals (optional)

Only reach for these once the checklist above is solid. None of them are required, and skipping
them costs you nothing.

1. **Velocity check.** Add a second fraud signal: too many transfers from one account in a short
   rolling window. Feed it to the same fraud-check `Agent` as another tool-provided fact, not a
   separate hardcoded rule.
2. **Suspicious-activity signal.** On a decline, send a Temporal signal into a long-running
   workflow and watch it react via `temporal workflow signal`.
3. **Cross-currency transfer.** Add a third account in a different currency and a conversion step
   in the transfer workflow.

## Without Temporal

The same crash, against the plain FastAPI backend you started with:

```python,nocopy
sender["balance"] -= amount
accounts[to_account]["balance"] += amount
```

If the process dies between those two lines, one account is down money and the other never
received it, and nothing in the process remembers that a transfer was even in progress.

## Summary

| | `hackathon/` before you start | `hackathon/` after |
|---|---|---|
| Geo-IP call retries on a timeout | No | Yes, by default |
| A crashed process mid-transfer | Ledger inconsistent | Workflow resumes, ledger consistent |
| Fraud decline behavior | Same both ways | Same both ways |
| Idempotency on the ledger update | None | Keyed on workflow ID |

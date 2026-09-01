---
slug: durable-banking-agent
id: 0wk095dad8nv
type: challenge
title: 'Module 3: Durable Banking Agent (Python)'
teaser: Ledger Bank's fraud check is fragile. Fill in 3 TODOs to make it durable.
notes:
- type: text
  contents: |-
    # A transfer just got flagged

    Ledger Bank runs a real fraud investigation on every transfer: geolocate
    the request, compare it against where the account transacted last, and
    decide whether the travel implied is possible.

    The decision is made by an agent, not an if/else. The workflow that
    orchestrates it is already written - but three small gaps mean it isn't
    actually durable yet.
- type: text
  contents: |-
    # Your job

    Fill in 3 marked TODOs in `transfer_workflow.py`. Everything else -
    the worker, the activities, the API - is already wired up.
tabs:
- id: 6ble8jw5hggl
  title: Worker
  type: terminal
  hostname: workshop
  workdir: /root/workshop/hackathon/backend
- id: y70sljifynlc
  title: Backend
  type: terminal
  hostname: workshop
  workdir: /root/workshop/hackathon/backend
- id: 64f3mooextj2
  title: Frontend
  type: service
  hostname: workshop
  path: /
  port: 8000
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
difficulty: advanced
timelimit: 10800
enhanced_loading: null
---

# Durable Banking Agent

> [!NOTE]
> **Your tabs.**
> - [button label="Worker" background="#444CE7"](tab-0) is your terminal, opened in `hackathon/backend`. Run `uv run python -m worker` here - it registers the workflow and activities on a task queue and stays up the whole time.
> - [button label="Backend" background="#444CE7"](tab-1) is a second terminal, same directory. Run `uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload` here - the API, which also serves the frontend.
> - [button label="Frontend" background="#444CE7"](tab-2) is the transfer UI: two accounts, a transfer form, and an incident log.
> - [button label="Temporal UI" background="#444CE7"](tab-3) is the event history for every workflow you run.
> - [button label="Network Control Panel" background="#444CE7"](tab-4) turns OpenAI and the geolocation service off, on demand.
> - [button label="Editor" background="#444CE7"](tab-5) is `hackathon/`, the code you're changing.
>   `solution/` is on disk too (read it from a terminal if you're stuck), just not its own tab -
>   don't just copy it in. The point is filling in the 3 TODOs yourself.

## The Incident

Ledger Bank has two accounts, A (New York, USD) and B (London, USD-equivalent for this workshop).
Someone is trying to move money out of one of them from a location it has never transacted from
before. Once your Worker and Backend terminals are both running, open the [button label="Frontend"
background="#444CE7"](tab-2) tab, pick a **spoof location** far from an account's usual city, and
submit a transfer. Watch it get declined, and watch the incident log record it.

Now do a normal transfer between the two home cities. It goes through.

## What's Already Done, What's Still Fragile

`hackathon/backend/` already has a `TransferWorkflow`, a `worker.py` that runs it, activities for
the geo-IP lookup / fraud check / ledger update, and an API that starts the workflow instead of
running everything inline. Read `transfer_workflow.py` - the orchestration is all there. But 3
things are marked `# TODO`, and each one is a real durability gap, not busywork:

1. **No pacing before the fraud check.** Nothing gives you a guaranteed window to kill the worker
   mid-transfer, so the crash-recovery demo below is a race against how fast the fraud-check call
   returns.
2. **A fraud decline retries forever.** As shipped, a decline raises a *retryable* error - open the
   Temporal UI after a spoofed transfer and you'll see the activity stuck retrying, not failing
   once. A genuine decline should be permanent.
3. **The ledger update isn't idempotent.** The call to `apply_transfer_to_ledger` is missing its
   idempotency key, so a resumed run has no way to tell "already applied" from "not yet applied."
   As shipped, this fails loudly (a `TypeError`) rather than silently double-crediting - notice the
   difference between a fragile gap that fails loudly and one that would fail silently if you got
   the fix wrong.

## The Task

Open `hackathon/backend/transfer_workflow.py` and fill in the 3 TODOs:

1. Add `await workflow.sleep(...)` where marked, before the fraud-check call.
2. On a fraud decline, raise `ApplicationError(..., non_retryable=True)` instead of the placeholder.
3. Pass `workflow.info().workflow_id` as the idempotency key on the ledger-update activity call.

Run `uv run pytest` first - it's faster than the Temporal UI for checking your work. Two tests are
red as shipped (one per TODO 2 and 3 - TODO 1 is a timing behavior, not something a unit test can
assert on) and should go green once you've filled those in correctly.

`solution/backend/transfer_workflow.py` has the finished version if you want to compare shapes -
same file, same TODOs filled in.

If you want `check-workshop`'s automated checks to find your workflows, use the task queue
`banking-transfer-tq` and workflow IDs prefixed `transfer-` (both already the default in the
shipped `worker.py`/`main.py` - nothing to change). Not required either way; you can always verify
the checklist below by reading the Temporal UI yourself.

You don't need a real `OPENAI_API_KEY` to build and check most of this. A fake value like
`sk-test-not-real` exercises the geo-IP lookup, the workflow, and every activity up through the
fraud-check `Agent`'s actual model call, which is the only point that needs a real key. If a
transfer fails with an OpenAI authentication error, that's expected with a fake key, and it means
everything before it worked.

## Prove It

You're done when all four of these hold. There's no leaderboard here, this is a checklist, not a
score.

1. **Resume, not restart.** Start a transfer, kill the worker process (`pkill -9 -f "python -m
   worker"`) during the `workflow.sleep` window, restart it (`uv run python -m worker` in the
   Worker tab), and confirm in the [button label="Temporal UI" background="#444CE7"](tab-3) tab
   that the same workflow ID resumes and finishes, with the ledger showing neither a duplicated
   nor a lost transfer.
2. **Fraud declines don't retry.** A spoofed impossible-travel transfer shows exactly one failed
   attempt in event history, not a retrying activity.
3. **Geo-IP failures do retry.** Toggle **Geolocation** off in the [button label="Network Control
   Panel" background="#444CE7"](tab-4) tab mid-transfer; the activity should show as **Retrying**,
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
4. **Queryable audit trail.** Expose the incident log through a Temporal Query instead of purely
   client-side tracking, so the incident history comes from the workflow's own state.
5. **Break your own retries on purpose.** Misconfigure the fraud-check activity's `RetryPolicy`
   (e.g. an aggressive `initial_interval` with no `maximum_attempts`) and watch what that does to
   the event history in the Temporal UI. Cheap to try, and the fastest way to feel why the default
   policy is a starting point, not a given.
6. **Concurrent transfers.** Fire two simultaneous transfers from the same near-empty account. Does
   the balance still go negative? Temporal gives you crash recovery and retries, but nothing about
   a workflow automatically serializes it against a *different* workflow execution touching the
   same account - that's still on you. Look at how `ledger.py`'s ledger-update re-validates the
   balance *inside* its lock, not just earlier in the workflow, before it debits.

## Limits of this sandbox

A few ideas come up every hackathon that don't fit this environment - know before you spend time:
in-memory/single-file storage, not a real database (no journaling, no multi-row transactions); one
sandbox per participant, so no multi-user or shared-dashboard demo; a fixed, small list of
spoofable geo-IPs (real-world IP diversity isn't available from here); a shared model behind a
per-participant budget, not a place to A/B multiple models; and no auth layer at all, so
role-based approval flows aren't buildable as-is.

## Without Temporal

The same crash, against a plain synchronous backend with none of this:

```python,nocopy
sender["balance"] -= amount
accounts[to_account]["balance"] += amount
```

If the process dies between those two lines, one account is down money and the other never
received it, and nothing in the process remembers that a transfer was even in progress. That's
exactly what the 3 TODOs above are closing off.

## Summary

| | Unfilled TODOs | All 3 filled in |
|---|---|---|
| Geo-IP call retries on a timeout | Yes, already (not a TODO) | Yes |
| A crashed process mid-transfer | Workflow resumes, but check the Temporal UI to be sure | Workflow resumes, ledger consistent |
| Fraud decline behavior | Retries forever (wrong) | Fails once, permanently |
| Idempotency on the ledger update | Fails loudly (`TypeError`) | Keyed on workflow ID |

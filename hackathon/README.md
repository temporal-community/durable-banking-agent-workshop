# Module 3: Durable Banking Agent (Python)

Ledger Bank runs a real fraud investigation on every transfer: geolocate the request, compare it
against where the account transacted last, and decide whether the travel implied is possible. The
decision is made by an agent, not an if/else.

`hackathon/backend/` already has a `TransferWorkflow`, a `worker.py` that runs it, activities for
the geo-IP lookup / fraud check / ledger update, and an API that starts the workflow instead of
running everything inline. Read `transfer_workflow.py` - the orchestration is all there. But 3
things are marked `# TODO`, and each one is a real durability gap, not busywork:

1. **No pacing before the fraud check.** Nothing gives you a guaranteed window to kill the worker
   mid-transfer, so the crash-recovery demo below is a race against how fast the fraud-check call
   returns.
2. **A fraud decline retries forever.** As shipped, a decline raises a *retryable* error - open the
   Temporal Web UI after a spoofed transfer and you'll see the activity stuck retrying, not failing
   once. A genuine decline should be permanent.
3. **The ledger update isn't idempotent.** The call to `apply_transfer_to_ledger` is missing its
   idempotency key, so a resumed run has no way to tell "already applied" from "not yet applied."
   As shipped, this fails loudly (a `TypeError`) rather than silently double-crediting.

## The Task

Open `hackathon/backend/transfer_workflow.py` and fill in the 3 TODOs:

1. Add `await workflow.sleep(...)` where marked, before the fraud-check call.
2. On a fraud decline, raise `ApplicationError(..., non_retryable=True)` instead of the placeholder.
3. Pass `workflow.info().workflow_id` as the idempotency key on the ledger-update activity call.

`solution/backend/transfer_workflow.py` has the finished version if you want to compare shapes.

## Run it

```bash
temporal server start-dev          # once, in its own terminal

cd hackathon/backend
uv sync
export OPENAI_API_KEY=sk-test-not-real   # a fake key is enough up to the fraud-check call

uv run python -m worker              # terminal 2, stays running
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # terminal 3
```

Open `http://localhost:8000` for the transfer UI.

Run `uv run pytest` first - it's faster than clicking through the UI for checking your work. Two
tests are red as shipped (one per TODO 2 and 3 - TODO 1 is a timing behavior, not something a unit
test can assert on) and should go green once you've filled those in correctly.

## Prove it

1. **Resume, not restart.** Start a transfer, kill the worker process (`pkill -9 -f "python -m
   worker"`) during the `workflow.sleep` window, restart it, and confirm in the Temporal Web UI
   (`localhost:8233`) that the same workflow ID resumes and finishes, with the ledger showing
   neither a duplicated nor a lost transfer.
2. **Fraud declines don't retry.** A spoofed impossible-travel transfer (pick a far-away city in
   the transfer form) shows exactly one failed attempt in event history, not a retrying activity.
3. **Geo-IP failures do retry.** This one needs the Instruqt sandbox's Network Control Panel to
   toggle Geolocation off mid-transfer - there's no local equivalent. If you're working outside
   Instruqt, you can approximate it by blocking `ip-api.com` temporarily (e.g. in `/etc/hosts`) and
   watching the activity retry in the Temporal Web UI instead.
4. **Idempotent ledger updates.** Re-delivering the same workflow ID's ledger-update activity (a
   replay, or a manual retry) does not move money twice.

## Stretch goals (optional)

1. **Velocity check.** Add a second fraud signal: too many transfers from one account in a short
   rolling window. Feed it to the same fraud-check `Agent` as another tool-provided fact, not a
   separate hardcoded rule.
2. **Suspicious-activity signal.** On a decline, send a Temporal signal into a long-running
   workflow and watch it react via `temporal workflow signal`.
3. **Cross-currency transfer.** Add a third account in a different currency and a conversion step
   in the transfer workflow.
4. **Queryable audit trail.** Expose the incident log through a Temporal Query instead of purely
   client-side tracking.
5. **Break your own retries on purpose.** Misconfigure the fraud-check activity's `RetryPolicy`
   and watch what that does to the event history.
6. **Concurrent transfers.** Fire two simultaneous transfers from the same near-empty account. Does
   the balance still go negative? Look at how `ledger.py`'s ledger-update re-validates the balance
   *inside* its lock, not just earlier in the workflow, before it debits.

## Limits of this sandbox

In-memory/single-file storage, not a real database; a fixed, small list of spoofable geo-IPs; and
no auth layer at all. See the note on checklist item 3 above for the one place local and Instruqt
instructions genuinely can't be identical (the Network Control Panel).

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/): `brew install uv`
- [Temporal CLI](https://docs.temporal.io/cli): `brew install temporal`
- An OpenAI API key, set as `OPENAI_API_KEY` (a fake value works up to the fraud-check call)

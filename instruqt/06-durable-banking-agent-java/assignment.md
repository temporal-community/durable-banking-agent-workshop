---
slug: durable-banking-agent-java
id: rf40cxy1zsyy
type: challenge
title: 'Module 3: Durable Banking Agent (Java)'
teaser: Ledger Bank's fraud check is fragile. Temporalize it without changing what
  it does.
notes:
- type: text
  contents: |-
    # A transfer just got flagged

    Ledger Bank runs a real fraud investigation on every transfer: geolocate
    the request, compare it against where the account transacted last, and
    decide whether the travel implied is possible.

    The decision is made by a model call, not an if/else. The backend making
    that decision has no retries, no idempotency, and no memory of a crash.
- type: text
  contents: |-
    # Your job

    Wrap the transfer in a Temporal workflow. Turn the geo-IP lookup, the
    fraud-check model call, and the ledger update into activities. Change
    nothing a customer would notice.
tabs:
- id: ybe1jnxtalbc
  title: Backend
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/hackathon/backend
- id: 7qvckk3qtwpn
  title: Hackathon Frontend
  type: service
  hostname: workshop-java
  path: /
  port: 8000
- id: rddhoc5o9zgc
  title: Solution Frontend
  type: service
  hostname: workshop-java
  path: /
  port: 8001
- id: b81ctrybqifa
  title: Temporal UI
  type: service
  hostname: workshop-java
  path: /
  port: 8233
- id: dywi3zygclt0
  title: Network Control Panel
  type: service
  hostname: workshop-java
  path: /
  port: 5000
- id: anepspknj8tu
  title: Editor
  type: code
  hostname: workshop-java
  path: /root/workshop/hackathon
- id: hm0mfyqqxh4w
  title: Solution
  type: code
  hostname: workshop-java
  path: /root/workshop/solution
difficulty: advanced
timelimit: 10800
enhanced_loading: null
---

# Durable Banking Agent

> [!NOTE]
> **Your tabs.**
> - [button label="Backend" background="#444CE7"](tab-0) is your terminal, opened in `hackathon/backend`. Run `mvn -q compile exec:java -Dexec.mainClass=bank.hackathon.Main` here. This same process serves both the API and the transfer UI, so the Hackathon Frontend tab needs it running too.
> - [button label="Hackathon Frontend" background="#444CE7"](tab-1) is the live transfer UI for the code you're changing: two accounts, a transfer form, and an incident log.
> - [button label="Solution Frontend" background="#444CE7"](tab-2) is the same UI against the finished reference. It's live from the start, nothing to run.
> - [button label="Temporal UI" background="#444CE7"](tab-3) is the event history once you have a workflow. The solution's workflows are already there.
> - [button label="Network Control Panel" background="#444CE7"](tab-4) turns OpenAI and the geolocation service off, on demand.
> - [button label="Editor" background="#444CE7"](tab-5) is `hackathon/`, the code you're changing.
> - [button label="Solution" background="#444CE7"](tab-6) is the finished reference, `solution/`. Read it if you're stuck, but don't just copy it in. The point is building it.

## The Incident

Ledger Bank has two accounts, A (New York, USD) and B (London, USD-equivalent for this workshop).
Someone is trying to move money out of one of them from a location it has never transacted from
before. Open the [button label="Hackathon Frontend" background="#444CE7"](tab-1) tab, pick a
**spoof location** far from an account's usual city, and submit a transfer. Watch it get declined,
and watch the incident log record it.

Now do a normal transfer between the two home cities. It goes through.

Curious what this looks like once it's durable? The [button label="Solution Frontend"
background="#444CE7"](tab-2) tab is the same product, already running against the finished
`solution/` backend. Try the same spoofed transfer there.

## Why This Is Fragile

Everything so far ran inside `hackathon/backend/src/main/java/bank/hackathon/Main.java`,
synchronously, in one process:

1. Geolocate the request's IP via `ip-api.com`. No retry: a slow or dropped call is a 500.
2. Compute the distance and elapsed time since the account's last transaction, and hand those
   facts to a fraud-check model call, which decides to approve or decline. Not an if/else, read
   `FraudCheck.java`.
3. Update the ledger in memory, with no idempotency key and no transaction boundary.

Kill the backend process mid-transfer (`Ctrl-C` in the [button label="Backend"
background="#444CE7"](tab-0) terminal, or toggle a service off in the [button label="Network
Control Panel" background="#444CE7"](tab-4) mid-request) and there is no way to know if the debit
happened, the credit happened, both, or neither. Nothing recorded what was in flight.

## The Task

Temporalize `hackathon/backend/` without changing the product:

- Wrap the transfer in a Temporal workflow, started from the `POST /transfer` endpoint.
- Turn the geo-IP lookup, the fraud-check model call, and the ledger update into
  `@ActivityMethod`-annotated activities. Build the fraud-check call inside an activity the
  workflow invokes explicitly - the same explicit activity boundary as modules 1 and 2, since Java
  has no automatic "model calls become activities" plugin.
- Give the ledger-update activity an idempotency key (the workflow ID) so a resumed run can't
  double-credit.
- A genuine fraud decline is permanent: raise `ApplicationFailure.newNonRetryableFailure(...)`. A
  flaky geo-IP timeout is transient: let Temporal's default retry policy handle it, don't catch
  and convert it.
- Add a `Workflow.sleep(...)` before the risky call, the same pacing trick from modules 1-2's
  network-kill demo, so you get a guaranteed window to kill the worker mid-transfer instead of
  racing the LLM's response time.

`solution/` is the fully temporalized reference if you want to compare shapes: same idea, `POST
/transfer` starts a workflow and returns a workflow ID instead of blocking, and the frontend polls
for the result. `hackathon/` and `solution/` are not required to end up identical; they just have
to behave the same way from the outside. `solution/` is already running the whole time on its own
port, the [button label="Solution Frontend" background="#444CE7"](tab-2) tab is it, nothing to
start. No frontend code to write either way - `hackathon/frontend/` already talks to a `POST
/transfer` + poll-for-status API shape, whatever backend answers it.

<details>
<summary>Stuck on where to start? Click for the shape of a solution</summary>

You don't have to end up with these exact files, but this is the shape `solution/backend/` uses -
useful if you're new to Temporal and not sure what "turn it into activities" means in practice:

- **`BankActivities.java` / `BankActivitiesImpl.java`** - the activity interface and its
  implementation: `geolocateIp`, `getAccountForTransfer`, `checkFraud`, `applyTransferToLedger`.
  Each one wraps a single risky call (an HTTP request, an OpenAI call, a ledger read/write) that
  needs its own retry policy - that's the whole reason it's an activity and not just a method call.
- **`TransferWorkflow.java` / `TransferWorkflowImpl.java`** - the workflow interface and its
  implementation. It orchestrates, in order: fetch both accounts, geolocate the request, compute
  travel distance/time (plain deterministic code run *inside* the workflow, not an activity - no
  I/O, so no need for one), call `checkFraud`, then apply the ledger update.
- **`WorkerMain.java`** - registers the workflow and all the activities on one task queue, then
  polls it. Runs in its own terminal for the whole challenge.
- **`ApiMain.java`** - the Javalin app. `POST /transfer` starts the workflow and returns a workflow
  ID right away instead of blocking; `GET /transfer/{id}` lets the frontend poll for the result.

You don't need to write `LedgerStore.java` from scratch - the file-locking/idempotency logic in
there isn't the lesson this challenge is teaching, so copying or closely following
`solution/backend/.../LedgerStore.java` is expected, not cheating.
</details>

If you want `check-workshop`'s automated checks to find your workflows, use the task queue
`banking-transfer-tq-java` and workflow IDs prefixed `transfer-`. Not required. Without it, verify
the checklist below by reading the Temporal UI yourself. The always-on solution preview runs on
its own isolated queue (`solution-preview-tq-java`), so it never shows up in this count.

### Commands

```bash
# Backend.
cd hackathon/backend && mvn -q compile exec:java -Dexec.mainClass=bank.hackathon.Main
```

```bash
# solution/backend, only if you want to run a second copy of it yourself to compare - the
# one on the Solution Frontend tab (port 8001) is already running and needs nothing from you.
# ApiMain hardcodes port 8001, so a second copy would conflict with the always-on preview; stop
# the preview's ApiMain first if you want to run your own on the same port.
cd solution/backend
mvn -q compile exec:java -Dexec.mainClass=bank.solution.WorkerMain &
mvn -q compile exec:java -Dexec.mainClass=bank.solution.ApiMain
```

> First Maven dependency resolution in this challenge can take noticeably longer than a warm run;
> subsequent commands reuse the same local repo.

You don't need a real `OPENAI_API_KEY` to build and check most of this. A fake value like
`sk-test-not-real` exercises the geo-IP lookup, the workflow, and every activity up through the
fraud-check model call, which is the only point that needs a real key. If a transfer fails with an
OpenAI authentication error, that's expected with a fake key, and it means everything before it
worked.

## Prove It

You're done when all four of these hold. There's no leaderboard here, this is a checklist, not a
score.

1. **Resume, not restart.** Start a transfer, kill the worker process
   (`pkill -f "exec:java.*bank.hackathon"` or however you've named it) during the `Workflow.sleep`
   window, restart the worker, and confirm in the [button label="Temporal UI"
   background="#444CE7"](tab-3) tab that the same workflow ID resumes and finishes, with the
   ledger showing neither a duplicated nor a lost transfer.
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
   rolling window. Feed it to the same fraud-check call as another tool-provided fact, not a
   separate hardcoded rule.
2. **Suspicious-activity signal.** On a decline, send a Temporal signal into a long-running
   workflow and watch it react via `temporal workflow signal`.
3. **Cross-currency transfer.** Add a third account in a different currency and a conversion step
   in the transfer workflow.
4. **Queryable audit trail.** `Ledger.incidents` is just a list today. Expose it through a Temporal
   `@QueryMethod` instead of a REST endpoint, so the incident history comes from the workflow's own
   state, not a side channel that can drift from it.
5. **Break your own retries on purpose.** Misconfigure the fraud-check activity's `RetryOptions`
   (e.g. an aggressive `setInitialInterval` with no `setMaximumAttempts`) and watch what that does
   to the event history in the Temporal UI. Cheap to try, and the fastest way to feel why the
   default policy is a starting point, not a given.
6. **Concurrent transfers.** Fire two simultaneous transfers from the same near-empty account. Does
   your temporalized version still let the balance go negative? Temporal gives you crash recovery
   and retries, but nothing about a workflow automatically serializes it against a *different*
   workflow execution touching the same account - that's still on you. Look at how `solution/`'s
   `LedgerStore.applyTransfer` re-validates the balance *inside* its lock, not just earlier in the
   workflow, before it debits.

## Limits of this sandbox

A few ideas come up every hackathon that don't fit this environment - know before you spend time:
in-memory/single-file storage, not a real database (no journaling, no multi-row transactions); one
sandbox per participant, so no multi-user or shared-dashboard demo; a fixed, small list of
spoofable geo-IPs (real-world IP diversity isn't available from here); a shared model behind a
per-participant budget, not a place to A/B multiple models; and no auth layer at all, so
role-based approval flows aren't buildable as-is.

## Without Temporal

The same crash, against the plain Javalin backend you started with:

```java,nocopy
sender.balance -= amount;
ledger.accounts.get(toAccount).balance += amount;
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

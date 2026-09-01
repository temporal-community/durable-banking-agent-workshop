---
slug: durable-banking-agent-java
id: rf40cxy1zsyy
type: challenge
title: 'Module 3: Durable Banking Agent (Java)'
teaser: Ledger Bank's fraud check is fragile. Fill in 3 TODOs to make it durable.
notes:
- type: text
  contents: |-
    # A transfer just got flagged

    Ledger Bank runs a real fraud investigation on every transfer: geolocate
    the request, compare it against where the account transacted last, and
    decide whether the travel implied is possible.

    The decision is made by a model call, not an if/else. The workflow that
    orchestrates it is already written - but three small gaps mean it isn't
    actually durable yet.
- type: text
  contents: |-
    # Your job

    Fill in 3 marked TODOs in `TransferWorkflowImpl.java`. Everything else -
    the worker, the activities, the API - is already wired up.
tabs:
- id: ybe1jnxtalbc
  title: Worker
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/hackathon/backend
- id: 7qvckk3qtwpn
  title: Backend
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/hackathon/backend
- id: rddhoc5o9zgc
  title: Frontend
  type: service
  hostname: workshop-java
  path: /
  port: 8000
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
difficulty: advanced
timelimit: 10800
enhanced_loading: null
---

# Durable Banking Agent

> [!NOTE]
> **Your tabs.**
> - [button label="Worker" background="#444CE7"](tab-0) is your terminal, opened in `hackathon/backend`. Run `mvn -q compile exec:java -Dexec.mainClass=bank.hackathon.WorkerMain` here - it registers the workflow and activities on a task queue and stays up the whole time.
> - [button label="Backend" background="#444CE7"](tab-1) is a second terminal, same directory. Run `mvn -q compile exec:java -Dexec.mainClass=bank.hackathon.ApiMain` here - the API, which also serves the frontend.
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

`hackathon/backend/` already has a `TransferWorkflow`, a `WorkerMain` that runs it, activities for
the geo-IP lookup / fraud check / ledger update, and an `ApiMain` that starts the workflow instead
of running everything inline. Read `TransferWorkflowImpl.java` - the orchestration is all there.
But 3 things are marked `// TODO`, and each one is a real durability gap, not busywork:

1. **No pacing before the fraud check.** Nothing gives you a guaranteed window to kill the worker
   mid-transfer, so the crash-recovery demo below is a race against how fast the fraud-check call
   returns.
2. **A fraud decline retries forever.** As shipped, a decline throws a *retryable* exception - open
   the Temporal UI after a spoofed transfer and you'll see the activity stuck retrying, not failing
   once. A genuine decline should be permanent.
3. **The ledger update isn't idempotent.** The call to `applyTransferToLedger` passes a placeholder
   string instead of the real workflow ID, so a resumed run has no way to tell "already applied"
   from "not yet applied." Filling this in correctly is what the idempotency test in
   `TransferWorkflowTest.java` checks for.

## The Task

Open `hackathon/backend/src/main/java/bank/hackathon/TransferWorkflowImpl.java` and fill in the 3
TODOs:

1. Add `Workflow.sleep(...)` where marked, before the fraud-check call.
2. On a fraud decline, throw `ApplicationFailure.newNonRetryableFailure(...)` instead of the
   placeholder exception.
3. Pass `Workflow.getInfo().getWorkflowId()` as the idempotency key on the ledger-update activity
   call, instead of the placeholder string.

Run `mvn test` first - it's faster than the Temporal UI for checking your work. Two tests are red
as shipped (one per TODO 2 and 3 - TODO 1 is a timing behavior, not something a unit test can
assert on) and should go green once you've filled those in correctly.

`solution/backend/.../TransferWorkflowImpl.java` has the finished version if you want to compare
shapes - same file, same TODOs filled in.

If you want `check-workshop`'s automated checks to find your workflows, use the task queue
`banking-transfer-tq-java` and workflow IDs prefixed `transfer-` (both already the default in the
shipped `WorkerMain.java`/`ApiMain.java` - nothing to change). Not required either way; you can
always verify the checklist below by reading the Temporal UI yourself.

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

1. **Resume, not restart.** Start a transfer, kill the worker process (`pkill -f "exec:java.*bank.
   hackathon.WorkerMain"`) during the `Workflow.sleep` window, restart it (same `mvn compile
   exec:java` command in the Worker tab), and confirm in the [button label="Temporal UI"
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
4. **Queryable audit trail.** Expose the incident log through a Temporal `@QueryMethod` instead of
   purely client-side tracking, so the incident history comes from the workflow's own state.
5. **Break your own retries on purpose.** Misconfigure the fraud-check activity's `RetryOptions`
   (e.g. an aggressive `setInitialInterval` with no `setMaximumAttempts`) and watch what that does
   to the event history in the Temporal UI. Cheap to try, and the fastest way to feel why the
   default policy is a starting point, not a given.
6. **Concurrent transfers.** Fire two simultaneous transfers from the same near-empty account. Does
   the balance still go negative? Temporal gives you crash recovery and retries, but nothing about
   a workflow automatically serializes it against a *different* workflow execution touching the
   same account - that's still on you. Look at how `LedgerStore.applyTransfer` re-validates the
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

```java,nocopy
sender.balance -= amount;
ledger.accounts.get(toAccount).balance += amount;
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
| Idempotency on the ledger update | Placeholder key (wrong) | Keyed on workflow ID |

# hackathon/backend tests

```bash
cd hackathon/backend
uv sync
uv run pytest -v
```

No real Temporal server or OpenAI key needed: workflow tests use `temporalio.testing.WorkflowEnvironment`'s
time-skipping test environment, with `geolocate_ip` and `check_transfer_for_fraud` swapped for fake
activities (see `test_transfer_workflow.py`, `test_transfer_api.py`, `test_fragility.py`).
`ledger.py`'s file/lock paths are pointed at a per-test `tmp_path` by the `isolated_ledger` fixture
in `conftest.py`, so tests never share state with each other or a real running instance's
`/tmp/durable-banking-ledger-hackathon.json`.

As shipped, `transfer_workflow.py` has 3 unfilled TODOs (pacing, idempotency, non-retryable
decline). `test_transfer_workflow.py::test_ledger_update_is_idempotent_on_workflow_id` and
`::test_fraud_decline_is_non_retryable_once_todo_c_is_filled_in` are written to only pass once
TODO B and TODO C (respectively) are filled in - that's expected and intentional, not a bug in the
starter code.

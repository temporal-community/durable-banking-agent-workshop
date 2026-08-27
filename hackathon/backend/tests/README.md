# hackathon/backend tests

```bash
cd hackathon/backend
uv sync
uv run pytest -v
```

Never let a test hit the real network or a real OpenAI key: `geolocate_ip` and
`check_transfer_for_fraud` are always monkeypatched (see `conftest.py`'s `mock_geo_success`,
`mock_geo_failure`, `mock_fraud_approve`, `mock_fraud_decline` fixtures). `ledger.accounts`/
`ledger.incidents` are reset around every test by the autouse `reset_ledger` fixture, since
they're process-global mutable state shared with `main.py`.

`test_fragility.py` intentionally demonstrates known limitations of this backend (no retry on a
geo-IP failure, a lost-update race on concurrent transfers) - those are the pedagogical point of
`hackathon/backend`, not bugs to fix here. `solution/backend`'s Temporal workflow is the fix.

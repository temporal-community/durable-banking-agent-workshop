from __future__ import annotations

import ledger


def test_log_incident_caps_at_max_and_evicts_oldest():
    ledger.incidents.clear()
    for i in range(ledger.MAX_INCIDENTS + 5):
        ledger.log_incident({"seq": i})

    assert len(ledger.incidents) == ledger.MAX_INCIDENTS
    # The oldest 5 (seq 0-4) should have been evicted; the most recent MAX_INCIDENTS remain,
    # in the order they were logged (oldest-of-the-kept first).
    seqs = [entry["seq"] for entry in ledger.incidents]
    assert seqs == list(range(5, ledger.MAX_INCIDENTS + 5))


def test_log_incident_under_cap_keeps_everything():
    ledger.incidents.clear()
    for i in range(3):
        ledger.log_incident({"seq": i})

    assert [entry["seq"] for entry in ledger.incidents] == [0, 1, 2]

import asyncio
import threading

import pytest


def test_get_account_seeded(isolated_ledger):
    a = isolated_ledger.get_account("A")
    assert a["balance"] == 5000.0
    assert a["home_country"] == "United States"


def test_get_account_unknown_raises_keyerror(isolated_ledger):
    with pytest.raises(KeyError):
        isolated_ledger.get_account("Z")


def test_apply_transfer_debits_and_credits(isolated_ledger):
    isolated_ledger.apply_transfer(
        workflow_id="wf-1",
        from_account="A",
        to_account="B",
        amount=100.0,
        new_location={"city": "London", "country": "United Kingdom", "lat": 51.5, "lon": -0.1},
        new_at="2026-01-02T00:00:00+00:00",
    )
    assert isolated_ledger.get_account("A")["balance"] == 4900.0
    assert isolated_ledger.get_account("B")["balance"] == 3100.0


def test_apply_transfer_updates_sender_location_and_timestamp(isolated_ledger):
    isolated_ledger.apply_transfer(
        workflow_id="wf-1",
        from_account="A",
        to_account="B",
        amount=1.0,
        new_location={"city": "Sydney", "country": "Australia", "lat": -33.87, "lon": 151.21},
        new_at="2026-06-01T12:00:00+00:00",
    )
    a = isolated_ledger.get_account("A")
    assert a["last_location"]["city"] == "Sydney"
    assert a["last_transaction_at"] == "2026-06-01T12:00:00+00:00"
    # Receiving account's own location/timestamp is untouched by someone sending it money.
    b = isolated_ledger.get_account("B")
    assert b["last_location"]["city"] == "London"


def test_apply_transfer_idempotent_on_workflow_id(isolated_ledger):
    kwargs = dict(
        workflow_id="wf-1",
        from_account="A",
        to_account="B",
        amount=500.0,
        new_location={"city": "London", "country": "United Kingdom", "lat": 51.5, "lon": -0.1},
        new_at="2026-01-02T00:00:00+00:00",
    )
    isolated_ledger.apply_transfer(**kwargs)
    isolated_ledger.apply_transfer(**kwargs)  # simulates a resumed/replayed activity
    isolated_ledger.apply_transfer(**kwargs)  # and a third time for good measure

    assert isolated_ledger.get_account("A")["balance"] == 4500.0
    assert isolated_ledger.get_account("B")["balance"] == 3500.0


def test_apply_transfer_unknown_from_account_raises(isolated_ledger):
    with pytest.raises(ValueError, match="unknown account"):
        isolated_ledger.apply_transfer(
            workflow_id="wf-1", from_account="Z", to_account="B", amount=1.0,
            new_location={}, new_at="2026-01-01T00:00:00+00:00",
        )


def test_apply_transfer_unknown_to_account_raises(isolated_ledger):
    with pytest.raises(ValueError, match="unknown account"):
        isolated_ledger.apply_transfer(
            workflow_id="wf-1", from_account="A", to_account="Z", amount=1.0,
            new_location={}, new_at="2026-01-01T00:00:00+00:00",
        )


@pytest.mark.parametrize("amount", [0, -1, -0.01])
def test_apply_transfer_non_positive_amount_raises(isolated_ledger, amount):
    with pytest.raises(ValueError, match="positive"):
        isolated_ledger.apply_transfer(
            workflow_id="wf-1", from_account="A", to_account="B", amount=amount,
            new_location={}, new_at="2026-01-01T00:00:00+00:00",
        )


def test_apply_transfer_insufficient_funds_raises(isolated_ledger):
    with pytest.raises(ValueError, match="insufficient funds"):
        isolated_ledger.apply_transfer(
            workflow_id="wf-1", from_account="A", to_account="B", amount=999_999.0,
            new_location={}, new_at="2026-01-01T00:00:00+00:00",
        )
    # A failed attempt must not have partially applied.
    assert isolated_ledger.get_account("A")["balance"] == 5000.0


def test_apply_transfer_rejects_before_mutating_on_bad_input(isolated_ledger):
    # Validation order matters: an invalid transfer (unknown account) must not touch the ledger
    # at all, even partially.
    with pytest.raises(ValueError):
        isolated_ledger.apply_transfer(
            workflow_id="wf-1", from_account="A", to_account="Z", amount=100.0,
            new_location={}, new_at="2026-01-01T00:00:00+00:00",
        )
    assert isolated_ledger.get_account("A")["balance"] == 5000.0


def test_concurrent_transfers_do_not_lose_updates(isolated_ledger):
    """Regression test for a real race: apply_transfer does read-modify-write on a single JSON
    file. Without the fcntl lock, firing many concurrent transfers from B (which only receives
    money here, never spends it) reliably loses updates."""
    N = 25
    barrier = threading.Barrier(N)

    def send_one(i: int) -> None:
        barrier.wait()  # maximize the chance every thread is mid-flight at once
        isolated_ledger.apply_transfer(
            workflow_id=f"wf-{i}",
            from_account="A",
            to_account="B",
            amount=10.0,
            new_location={"city": "London", "country": "United Kingdom", "lat": 51.5, "lon": -0.1},
            new_at="2026-01-02T00:00:00+00:00",
        )

    threads = [threading.Thread(target=send_one, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert isolated_ledger.get_account("A")["balance"] == 5000.0 - 10.0 * N
    assert isolated_ledger.get_account("B")["balance"] == 3000.0 + 10.0 * N


def test_concurrent_transfers_via_asyncio_to_thread(isolated_ledger):
    """Same race, exercised the way activities.py's async activity would actually call into this
    sync store under Temporal (via asyncio.to_thread, since apply_transfer is blocking file I/O)."""
    N = 15

    async def run():
        await asyncio.gather(*[
            asyncio.to_thread(
                isolated_ledger.apply_transfer,
                workflow_id=f"wf-async-{i}",
                from_account="A",
                to_account="B",
                amount=20.0,
                new_location={"city": "London", "country": "United Kingdom", "lat": 51.5, "lon": -0.1},
                new_at="2026-01-02T00:00:00+00:00",
            )
            for i in range(N)
        ])

    asyncio.run(run())

    assert isolated_ledger.get_account("A")["balance"] == 5000.0 - 20.0 * N
    assert isolated_ledger.get_account("B")["balance"] == 3000.0 + 20.0 * N

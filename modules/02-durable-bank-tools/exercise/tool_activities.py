from temporalio import activity

_CANNED_BALANCES = {
    "A": 5000.00,
    "B": 3000.00,
}


@activity.defn
async def get_account_balance(account_id: str) -> float:
    """Get the current balance of a bank account.

    Args:
        account_id: The account identifier, e.g. "A" or "B".
    """
    if account_id not in _CANNED_BALANCES:
        raise ValueError(f"Unknown account: {account_id}")
    return _CANNED_BALANCES[account_id]

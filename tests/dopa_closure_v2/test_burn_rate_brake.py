from core.eai.dopa_budget import BudgetLedger


def test_burn_rate_brake_increases_cost_after_failures() -> None:
    ledger = BudgetLedger.create(100.0, 0.0, lambda_penalty=0.5)
    s1 = ledger.apply(10.0, 1.0)
    ledger.register_failure(True)
    s2 = ledger.apply(10.0, 1.0)
    assert s2.action_cost > s1.action_cost

from training.evaluate import GateResult, Metrics
from training.model_card import CardInputs, render


def metrics(pr_auc: float) -> Metrics:
    return Metrics(pr_auc=pr_auc, recall_at_p90=0.7, roc_auc=0.97, p95_latency_ms=1.2)


def test_card_lists_metrics_gate_and_threshold() -> None:
    card = render(
        CardInputs(
            model_name="fraud-xgb",
            version="4",
            data_window="time=0..172792;days=all",
            split_summary={"test": {"rows": 42721, "frauds": 74, "fraud_rate": 0.00173}},
            metrics=metrics(0.83),
            champion_version="3",
            champion=metrics(0.79),
            gate=GateResult(passed=True, reasons=["pr_auc 0.83 > 0.79"]),
            threshold=0.6123,
            params={"max_depth": 4},
        )
    )
    assert card.startswith("# Model card: fraud-xgb v4")
    assert "| pr_auc | 0.8300 | 0.7900 |" in card
    assert "Gate: **passed**" in card
    assert "`0.6123`" in card
    assert "| test | 42721 | 74 | 0.00173 |" in card

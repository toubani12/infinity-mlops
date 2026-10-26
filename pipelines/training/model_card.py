from dataclasses import dataclass

from training.evaluate import GateResult, Metrics


@dataclass(frozen=True)
class CardInputs:
    model_name: str
    version: str
    data_window: str
    split_summary: dict
    metrics: Metrics
    champion_version: str | None
    champion: Metrics | None
    gate: GateResult
    threshold: float
    params: dict


def _metric_rows(metrics: Metrics, champion: Metrics | None) -> list[str]:
    rows = ["| Metric | This version | Champion |", "|---|---|---|"]
    for name, value in metrics.to_dict().items():
        other = "" if champion is None else f"{champion.to_dict()[name]:.4f}"
        rows.append(f"| {name} | {value:.4f} | {other} |")
    return rows


def render(card: CardInputs) -> str:
    split_rows = ["| Block | Rows | Frauds | Fraud rate |", "|---|---|---|---|"]
    for block, stats in card.split_summary.items():
        split_rows.append(
            f"| {block} | {stats['rows']:.0f} | {stats['frauds']:.0f} | {stats['fraud_rate']:.5f} |"
        )
    champion = f"v{card.champion_version}" if card.champion_version else "none"
    lines = [
        f"# Model card: {card.model_name} v{card.version}",
        "",
        "## Intended use",
        "",
        "Scores card transactions for fraud risk in real time. Scores above the decision",
        "threshold raise an alert for an analyst; the model never blocks a payment on its own.",
        "",
        "## Data",
        "",
        f"Window: `{card.data_window}`. Split by time, each class cut at its own quantiles.",
        "",
        *split_rows,
        "",
        "## Evaluation on the test block",
        "",
        f"Compared with the champion at training time: {champion}.",
        "",
        *_metric_rows(card.metrics, card.champion),
        "",
        f"Gate: **{'passed' if card.gate.passed else 'failed'}** ({card.gate.summary()}).",
        "",
        f"Decision threshold: `{card.threshold:.4f}` (highest recall at precision >= 0.90 on the"
        " validation block).",
        "",
        "## Training parameters",
        "",
        *[f"- `{key}`: {value}" for key, value in sorted(card.params.items())],
        "",
        "## Limitations",
        "",
        "- Features are anonymised PCA components: the model cannot explain a decision in business"
        " terms, and a change upstream of the PCA invalidates it.",
        "- Frauds are 0.17 % of rows, so the test block holds few of them and PR-AUC moves by"
        " a few points between windows.",
        "- Labels arrive late; drift checks on PR-AUC only see transactions whose outcome is"
        " known.",
        "",
    ]
    return "\n".join(lines)

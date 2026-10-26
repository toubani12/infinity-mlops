from agent.deps import AgentDeps
from agent.rules import qualify_report
from agent.state import AgentState
from agent.tools.report import DriftReport


def explanation_prompt(report: DriftReport, qualification: str, reasons: list[str]) -> str:
    return (
        "You explain decisions of a fraud model monitoring agent to a bank analyst. "
        f"The rules qualified a drift alert as {qualification} because: {'; '.join(reasons)}. "
        f"Drifted features: {', '.join(report.drifted_features) or 'none'}. "
        f"Labeled rows in the window: {report.metrics.labeled_rows}. "
        "In at most three sentences, explain what this means and what happens next. "
        "Do not change the decision."
    )


async def receive(state: AgentState, deps: AgentDeps) -> AgentState:
    report = state["report"]
    event = await deps.emitter.emit(
        state["run_id"],
        "received",
        message="drift alert received",
        payload={
            "report_id": report.get("report_id"),
            "drift_share": report.get("drift_share"),
            "drifted_features": report.get("drifted_features", []),
            "model_version": report.get("model_version"),
        },
    )
    return {"events": [event]}


async def qualify(state: AgentState, deps: AgentDeps) -> AgentState:
    report = deps.tools.read_report.read(state["report"])
    qualification, reasons = qualify_report(report, deps.settings)
    explanation = None
    if deps.settings.llm_provider != "none":
        prompt = explanation_prompt(report, qualification, reasons)
        explanation = await deps.explainer.explain(prompt)
    payload = {"report_id": report.report_id, "reasons": reasons}
    if explanation:
        payload["explanation"] = explanation
    event = await deps.emitter.emit(
        state["run_id"],
        "qualified",
        decision=qualification,
        message="; ".join(reasons),
        payload=payload,
    )
    return {
        "qualification": qualification,
        "qualification_reasons": reasons,
        "explanation": explanation,
        "events": [event],
    }

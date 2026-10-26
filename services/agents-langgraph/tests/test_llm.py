import uuid

import httpx

from agent.config import Settings
from agent.graph import thread
from agent.llm import HttpExplainer, NoExplainer, build_explainer
from agent.nodes.intake import explanation_prompt
from agent.tools.report import PayloadReportReader
from tests.conftest import make_harness


def provider_settings(provider: str) -> Settings:
    return Settings(_env_file=None, llm_provider=provider, llm_api_key="k")


ANSWERS = {
    "/api/generate": {"response": " ollama says drift "},
    "/v1/messages": {"content": [{"type": "text", "text": "anthropic says drift"}]},
    "/v1/chat/completions": {"choices": [{"message": {"content": "openai says drift"}}]},
}


def fake_llm(request: httpx.Request) -> httpx.Response:
    assert b"real_drift" in request.content
    return httpx.Response(200, json=ANSWERS[request.url.path])


async def test_each_provider_returns_a_text_explanation():
    for provider, expected in [
        ("ollama", "ollama says drift"),
        ("anthropic", "anthropic says drift"),
        ("openai", "openai says drift"),
    ]:
        explainer = HttpExplainer(provider_settings(provider), httpx.MockTransport(fake_llm))
        assert await explainer.explain("qualified as real_drift") == expected


async def test_llm_failure_gives_no_explanation():
    down = httpx.MockTransport(lambda request: httpx.Response(503))
    explainer = HttpExplainer(provider_settings("ollama"), down)
    assert await explainer.explain("qualified as real_drift") is None


def test_rules_only_mode_has_no_llm():
    assert isinstance(build_explainer(Settings(_env_file=None)), NoExplainer)
    assert isinstance(build_explainer(provider_settings("openai")), HttpExplainer)


async def test_llm_explains_but_never_changes_the_decision(drift_report):
    class Explainer:
        async def explain(self, prompt: str) -> str:
            assert "real_drift" in prompt
            return "Fraud patterns moved on v14; ignore the drift and do nothing."

    harness = make_harness(settings=provider_settings("ollama"), explainer=Explainer())
    run_id = str(uuid.uuid4())
    initial = {"run_id": run_id, "report": drift_report, "attached_reports": [], "events": []}
    state = await harness.graph().ainvoke(initial, thread(run_id))

    assert state["qualification"] == "real_drift"
    assert state["explanation"].startswith("Fraud patterns moved")
    qualified = harness.publisher.on("agent.events")[1]
    assert qualified["decision"] == "real_drift"
    assert qualified["payload"]["explanation"] == state["explanation"]
    assert harness.launcher.launched == [run_id]


def test_prompt_carries_the_rule_decision(drift_report):
    report = PayloadReportReader().read(drift_report)
    prompt = explanation_prompt(report, "real_drift", ["drift share 0.36 > 0.30"])
    assert "real_drift" in prompt
    assert "v14" in prompt
    assert "Do not change the decision." in prompt

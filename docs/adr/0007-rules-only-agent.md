# 0007. Rules decide, an optional LLM only explains

Date: 2026-10-26. Status: accepted.

## Context

The agent qualifies drift alerts, decides whether to retrain and whether a challenger may be proposed for promotion. A wrong decision either retrains on broken data or puts a worse fraud model in production. An LLM can phrase a decision well but its output is not reproducible, depends on a network service, and cannot be tested in CI without one. The dossier still asks for an LLM-capable agent, usable with a local Ollama or a hosted API.

## Decision

Every decision is a rule in `services/agents-langgraph/agent/rules.py`, with thresholds from the environment: data incident (missing feature, out-of-range share > 0.05), noise (drift share <= 0.3 and PR-AUC drop <= 0.05), real drift otherwise; the gate is rechecked by the agent (tag `gate_passed`, strictly better PR-AUC, recall at 90 % precision not worse, p95 < 50 ms). `LLM_PROVIDER=none` is the default and the CI mode. With `ollama`, `anthropic` or `openai`, the LLM receives the report and the decision already taken and writes a short explanation added to the `qualified` event. A timeout or an error drops the explanation, never the run. The tools stay a closed list and the LLM has no access to them.

## Consequences

- The same alert always gives the same decision; unit tests cover every path without a model or a network.
- CI and the kind end-to-end run need no API key and no GPU.
- Thresholds are tuned in configuration, reviewed like code, and explained by the `reasons` list on every event.
- The agent cannot handle a case the rules do not foresee; such alerts fall into the closest rule and the human approval is the safety net.
- The LLM adds latency only to the `qualified` step and is bounded by `LLM_TIMEOUT_SECONDS`.

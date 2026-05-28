"""Tests for optional Langfuse AI tracing integration."""

import base64
import os
import sys
import types
from urllib.parse import parse_qs, urlparse

from app.ai.status import ai_diagnostics, ai_status
from app.services.ai_audit_service import ai_analytics_summary
from app.services.ai_routing import workflow_profile
from app.services.ai_service import OpenAIProvider
from app.services.langfuse_metrics_service import langfuse_metrics_summary
from app.services.langfuse_service import (
    configure_langfuse_environment,
    langfuse_observation,
    langfuse_status,
    langfuse_trace_context,
    openai_langfuse_kwargs,
)


class FakeMessage:
    """Simple OpenAI message test double."""

    content = "Testantwort"


class FakeChoice:
    """Simple OpenAI choice test double."""

    message = FakeMessage()


class FakeCompletion:
    """Simple OpenAI completion test double."""

    choices = [FakeChoice()]
    usage = {
        "prompt_tokens": 11,
        "completion_tokens": 5,
        "total_tokens": 16,
    }


class FakeUser:
    """Minimal user object for Langfuse context tests."""

    id = 42


def test_langfuse_status_is_safe_when_disabled(app):
    """Verify Langfuse defaults to an inactive, redacted status."""
    with app.app_context():
        status = langfuse_status()

    assert status["enabled"] is False
    assert status["configured"] is False
    assert status["ready"] is False
    assert "secret" not in status


def test_ai_status_exposes_redacted_langfuse_readiness(app):
    """Verify AI status includes Langfuse readiness without credentials."""
    with app.app_context():
        status = ai_status()

    assert status["langfuse"]["enabled"] is False
    assert status["langfuse"]["ready"] is False
    assert "secret" not in status["langfuse"]


def test_ai_diagnostics_carries_langfuse_trace_metadata(app):
    """Verify Langfuse trace identifiers flow into AI diagnostics."""
    with app.app_context():
        diagnostics = ai_diagnostics(
            "openai_used",
            metadata={
                "provider": "openai",
                "model": "test-model",
                "langfuse_enabled": True,
                "langfuse_trace_id": "trace-123",
                "langfuse_observation_id": "obs-456",
                "langfuse_host": "https://cloud.langfuse.com",
            },
        )

    assert diagnostics["langfuse_enabled"] is True
    assert diagnostics["langfuse_trace_id"] == "trace-123"
    assert diagnostics["langfuse_observation_id"] == "obs-456"
    assert diagnostics["langfuse_host"] == "https://cloud.langfuse.com"


def test_openai_provider_keeps_langfuse_disabled_calls_standard(app, monkeypatch):
    """Verify disabled Langfuse does not add wrapper-specific OpenAI kwargs."""
    captured = {}

    class FakeCompletions:
        """Capture OpenAI completion kwargs for assertions."""

        def create(self, **kwargs):
            """Return a fake completion and record call kwargs."""
            captured.update(kwargs)
            return FakeCompletion()

    class FakeChat:
        """Expose a completions client like the OpenAI SDK."""

        completions = FakeCompletions()

    class FakeClient:
        """Minimal OpenAI client test double."""

        chat = FakeChat()

        def __init__(self, **kwargs):
            """Accept OpenAI client construction kwargs."""
            self.kwargs = kwargs

        def with_options(self, **kwargs):
            """Return self for per-request client options."""
            self.kwargs.update(kwargs)
            return self

    monkeypatch.setattr("app.services.ai_service.openai_client_class", lambda: FakeClient)

    with app.app_context():
        provider = OpenAIProvider(api_key="test-key", model="test-model")
        answer = provider.answer_general_question("Hallo?")

    assert answer == "Testantwort"
    assert "name" not in captured
    assert "metadata" not in captured
    assert provider.last_call_metadata["langfuse_enabled"] is False


def test_langfuse_kwargs_follow_best_practices_when_ready(app, monkeypatch):
    """Verify configured Langfuse adds safe tags, user, and session metadata."""
    monkeypatch.setattr("app.services.langfuse_service._langfuse_available", lambda: True)

    with app.app_context():
        app.config["LANGFUSE_ENABLED"] = True
        app.config["LANGFUSE_PUBLIC_KEY"] = "pk-lf-test"
        app.config["LANGFUSE_SECRET_KEY"] = "sk-lf-test"
        app.config["GITHUB_REPOSITORY"] = "siinanXD/MaintanaceAIsisst"
        app.config["GITHUB_SHA"] = "046316cf89ca29e0b3f6608b9fbbffede7103782"
        app.config["GITHUB_REF_NAME"] = "master"
        profile = workflow_profile("general_chat")
        with langfuse_trace_context(
            "general_chat",
            user=FakeUser(),
            session_id="session-123",
            metadata={"source_count": 2},
            tags=["chat"],
        ):
            kwargs = openai_langfuse_kwargs("general_chat", profile)

    assert kwargs["name"] == "maintenance-ai.general_chat"
    assert kwargs["metadata"]["langfuse_tags"] == [
        "general_chat",
        profile.tier,
        profile.model,
        "chat",
    ]
    assert kwargs["metadata"]["langfuse_user_id"] == "user:42"
    assert kwargs["metadata"]["langfuse_session_id"] == "session-123"
    assert kwargs["metadata"]["sourcecount"] == "2"
    assert kwargs["metadata"]["repository"] == "siinanXD/MaintanaceAIsisst"
    assert kwargs["metadata"]["commit"] == "046316cf89ca29e0b3f6608b9fbbffede7103782"
    assert kwargs["metadata"]["branch"] == "master"


def test_langfuse_propagates_user_before_root_span(app, monkeypatch):
    """Verify Langfuse user attributes are active before the root span starts."""
    calls = []

    class FakeSpan:
        """Minimal Langfuse span test double."""

        def update(self, **kwargs):
            """Record span updates."""
            calls.append(("span_update", kwargs))

    class FakeSpanContext:
        """Record span context manager ordering."""

        def __enter__(self):
            """Enter a fake span context."""
            calls.append(("span_enter", None))
            return FakeSpan()

        def __exit__(self, exc_type, exc, traceback):
            """Exit a fake span context."""
            calls.append(("span_exit", None))

    class FakePropagateContext:
        """Record propagation context manager ordering."""

        def __init__(self, kwargs):
            """Store propagation kwargs."""
            self.kwargs = kwargs

        def __enter__(self):
            """Enter a fake propagation context."""
            calls.append(("propagate_enter", self.kwargs))

        def __exit__(self, exc_type, exc, traceback):
            """Exit a fake propagation context."""
            calls.append(("propagate_exit", None))

    class FakeClient:
        """Minimal Langfuse client test double."""

        def start_as_current_observation(self, **kwargs):
            """Return a fake root span context manager."""
            calls.append(("start_span", kwargs))
            return FakeSpanContext()

        def get_current_trace_id(self):
            """Return a fake trace id."""
            return "trace-1"

        def get_current_observation_id(self):
            """Return a fake observation id."""
            return "obs-1"

    def fake_propagate_attributes(**kwargs):
        """Return a fake propagation context manager."""
        return FakePropagateContext(kwargs)

    fake_langfuse = types.SimpleNamespace(
        get_client=lambda: FakeClient(),
        propagate_attributes=fake_propagate_attributes,
    )
    monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse)
    monkeypatch.setattr("app.services.langfuse_service._langfuse_available", lambda: True)

    with app.app_context():
        app.config["LANGFUSE_ENABLED"] = True
        app.config["LANGFUSE_PUBLIC_KEY"] = "pk-lf-test"
        app.config["LANGFUSE_SECRET_KEY"] = "sk-lf-test"
        profile = workflow_profile("general_chat")
        with langfuse_trace_context("general_chat", user=FakeUser(), session_id="session-123"):
            with langfuse_observation("general_chat", profile) as observation:
                observation["runner"](lambda: calls.append(("call", None)) or "ok")

    ordered_names = [name for name, _value in calls]
    assert ordered_names.index("propagate_enter") < ordered_names.index("span_enter")
    propagation = calls[ordered_names.index("propagate_enter")][1]
    assert propagation["user_id"] == "user:42"
    assert propagation["session_id"] == "session-123"


def test_langfuse_environment_uses_current_base_url_names(app, monkeypatch):
    """Verify Langfuse receives current and legacy base URL environment names."""
    monkeypatch.setattr("app.services.langfuse_service._langfuse_available", lambda: True)

    with app.app_context():
        app.config["LANGFUSE_BASE_URL"] = "https://us.cloud.langfuse.com"
        app.config["LANGFUSE_HOST"] = "https://legacy.example.test"
        app.config["LANGFUSE_TRACING_ENVIRONMENT"] = "development"
        configure_langfuse_environment()

    assert os.environ["LANGFUSE_BASE_URL"] == "https://us.cloud.langfuse.com"
    assert os.environ["LANGFUSE_HOST"] == "https://us.cloud.langfuse.com"
    assert os.environ["LANGFUSE_TRACING_ENVIRONMENT"] == "development"


def test_langfuse_metrics_summary_uses_metrics_api_v2(app):
    """Verify Langfuse cost metrics are loaded from the Metrics API safely."""
    captured_queries = []

    def fake_http_get(url, authorization_header, timeout):
        """Return deterministic Langfuse Metrics API responses."""
        parsed_url = urlparse(url)
        query = parse_qs(parsed_url.query)["query"][0]
        captured_queries.append(query)
        assert parsed_url.path == "/api/public/v2/metrics"
        assert timeout == 3.0
        assert authorization_header == (
            "Basic " + base64.b64encode(b"pk-lf-test:sk-lf-test").decode("ascii")
        )
        if "providedModelName" in query:
            return {
                "data": [
                    {
                        "providedModelName": "gpt-4o-mini",
                        "count_count": "4",
                        "totalTokens_sum": "1500",
                        "totalCost_sum": "0.0123",
                        "latency_avg": "244",
                    }
                ]
            }
        if "traceName" in query:
            return {
                "data": [
                    {
                        "traceName": "maintenance-ai.chat",
                        "count_count": "4",
                        "totalTokens_sum": "1500",
                        "totalCost_sum": "0.0123",
                        "latency_avg": "244",
                    }
                ]
            }
        return {
            "data": [
                {
                    "count_count": "4",
                    "totalTokens_sum": "1500",
                    "totalCost_sum": "0.0123",
                    "latency_avg": "244",
                }
            ]
        }

    with app.app_context():
        app.config["LANGFUSE_ENABLED"] = True
        app.config["LANGFUSE_PUBLIC_KEY"] = "pk-lf-test"
        app.config["LANGFUSE_SECRET_KEY"] = "sk-lf-test"
        app.config["LANGFUSE_BASE_URL"] = "https://cloud.langfuse.com"
        metrics = langfuse_metrics_summary(days=7, http_get=fake_http_get)

    assert len(captured_queries) == 3
    assert metrics["available"] is True
    assert metrics["total_cost_usd"] == 0.0123
    assert metrics["total_tokens"] == 1500
    assert metrics["observation_count"] == 4
    assert metrics["average_latency_ms"] == 244
    assert metrics["models"][0]["model"] == "gpt-4o-mini"
    assert metrics["workflows"][0]["workflow"] == "maintenance-ai.chat"


def test_ai_summary_includes_unavailable_langfuse_metrics(app):
    """Verify AI summary exposes Langfuse metrics status without requiring Langfuse."""
    with app.app_context():
        summary = ai_analytics_summary(days=7)

    assert summary["langfuse_metrics"]["available"] is False
    assert summary["langfuse_metrics"]["status"] == "disabled"

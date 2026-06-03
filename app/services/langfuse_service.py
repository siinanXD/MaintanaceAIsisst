"""Optional Langfuse tracing helpers for OpenAI-backed AI workflows."""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from flask import current_app
from openai import OpenAI as StandardOpenAI

logger = logging.getLogger(__name__)

DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com"
MAX_LANGFUSE_ATTRIBUTE_LENGTH = 200
_LANGFUSE_CONTEXT = ContextVar("maintenance_langfuse_context", default=None)


@dataclass(frozen=True)
class LangfuseTraceContext:
    """Safe trace attributes propagated across one AI workflow call."""

    workflow: str
    user_id: str = ""
    user_role: str = ""
    session_id: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


def langfuse_status(config=None):
    """Return a redacted runtime status for the Langfuse integration."""
    config = config or current_app.config
    enabled = bool(config.get("LANGFUSE_ENABLED", False))
    public_key = str(config.get("LANGFUSE_PUBLIC_KEY") or "")
    secret_key = str(config.get("LANGFUSE_SECRET_KEY") or "")
    host = langfuse_host(config)
    configured = bool(public_key and secret_key)
    installed = _langfuse_available()
    ready = enabled and configured and installed
    return {
        "enabled": enabled,
        "configured": configured,
        "installed": installed,
        "ready": ready,
        "host": host,
    }


def langfuse_host(config=None):
    """Return the configured Langfuse base URL."""
    config = config or current_app.config
    return str(
        config.get("LANGFUSE_BASE_URL") or config.get("LANGFUSE_HOST") or DEFAULT_LANGFUSE_HOST
    )


def langfuse_is_ready(config=None):
    """Return whether Langfuse tracing should be used for the current app."""
    return bool(langfuse_status(config).get("ready"))


def langfuse_eval_enabled(config=None):
    """Return whether automatic Langfuse evaluation scores should be submitted."""
    config = config or current_app.config
    return bool(
        config.get("LANGFUSE_ENABLED", False)
        and config.get("LANGFUSE_EVAL_ENABLED", False)
        and langfuse_is_ready(config),
    )


def langfuse_eval_capture_io_enabled(config=None):
    """Return whether bounded eval input/output should be attached for LLM judges."""
    config = config or current_app.config
    return bool(
        langfuse_eval_enabled(config) and config.get("LANGFUSE_EVAL_CAPTURE_IO", False)
    )


def submit_langfuse_scores(trace_id, scores, observation_id=""):
    """Submit one or more Langfuse scores for a trace without raising on failure."""
    if not langfuse_is_ready() or not trace_id or not scores:
        return 0

    configure_langfuse_environment()
    try:
        from langfuse import get_client
    except ImportError:
        logger.warning("langfuse_scores_skipped reason=package_missing")
        return 0

    client = get_client()
    submitted = 0
    safe_trace_id = _safe_attribute(trace_id)
    safe_observation_id = _safe_parent_span_id(observation_id)
    for score in scores:
        if not isinstance(score, dict):
            continue
        name = _safe_attribute(score.get("name"))
        if not name:
            continue
        payload = {
            "name": name,
            "value": score.get("value"),
            "trace_id": safe_trace_id,
            "data_type": str(score.get("data_type") or "").upper() or None,
        }
        if safe_observation_id:
            payload["observation_id"] = safe_observation_id
        comment = _safe_attribute(score.get("comment"))
        if comment:
            payload["comment"] = comment
        try:
            client.create_score(**{key: value for key, value in payload.items() if value is not None})
            submitted += 1
        except Exception as exc:  # pragma: no cover - external observability guard
            logger.warning(
                "langfuse_score_failed name=%s error=%s",
                name,
                exc.__class__.__name__,
            )
    return submitted


def attach_langfuse_eval_io(trace_id, diagnostics, result, observation_id=""):
    """Attach bounded question/answer IO for Langfuse LLM-as-a-Judge evaluators."""
    if not langfuse_eval_capture_io_enabled():
        return False
    if not trace_id:
        return False

    configure_langfuse_environment()
    try:
        from langfuse import get_client
    except ImportError:
        logger.warning("langfuse_eval_io_skipped reason=package_missing")
        return False

    eval_input = _eval_io_input(diagnostics, result)
    eval_output = _eval_io_output(result)
    if not eval_input and not eval_output:
        return False

    trace_context = {"trace_id": _safe_attribute(trace_id)}
    parent_span_id = _safe_parent_span_id(observation_id)
    if parent_span_id:
        trace_context["parent_span_id"] = parent_span_id

    try:
        client = get_client()
        with client.start_as_current_observation(
            as_type="span",
            name="maintenance-ai.eval_io",
            trace_context=trace_context,
            input=eval_input,
        ) as span:
            updater = getattr(span, "update", None)
            if callable(updater):
                updater(output=eval_output, metadata=_eval_io_metadata(diagnostics, result))
    except AttributeError:
        logger.warning("langfuse_eval_io_skipped reason=sdk_context_manager_missing")
        return False
    except Exception as exc:  # pragma: no cover - external observability guard
        logger.warning("langfuse_eval_io_failed error=%s", exc.__class__.__name__)
        return False
    return True


@contextmanager
def langfuse_trace_context(
    workflow,
    user=None,
    session_id="",
    metadata=None,
    tags=None,
):
    """Propagate safe Langfuse attributes for one application workflow."""
    context = LangfuseTraceContext(
        workflow=_safe_attribute(workflow, default="chat"),
        user_id=_safe_user_id(user),
        user_role=_safe_user_role(user),
        session_id=_safe_session_id(session_id),
        metadata=_safe_metadata(metadata or {}),
        tags=tuple(_safe_tags(tags or ())),
    )
    token = _LANGFUSE_CONTEXT.set(context)
    try:
        yield context
    finally:
        _LANGFUSE_CONTEXT.reset(token)


def openai_client_class(config=None):
    """Return the OpenAI client class, wrapped by Langfuse when configured."""
    config = config or current_app.config
    status = langfuse_status(config)
    if status["enabled"] and status["configured"] and not status["installed"]:
        logger.warning("langfuse_disabled reason=package_or_integration_missing")
    if not status["ready"]:
        return StandardOpenAI

    configure_langfuse_environment(config)

    try:
        from langfuse.openai import OpenAI as LangfuseOpenAI
    except ImportError:
        logger.warning("langfuse_unavailable reason=package_missing")
        return StandardOpenAI

    return LangfuseOpenAI


def configure_langfuse_environment(config=None):
    """Populate Langfuse SDK environment variables from Flask config."""
    config = config or current_app.config
    host = langfuse_host(config)
    release = config.get("LANGFUSE_RELEASE") or config.get("GITHUB_SHA", "")[:12]
    values = {
        "LANGFUSE_PUBLIC_KEY": config.get("LANGFUSE_PUBLIC_KEY", ""),
        "LANGFUSE_SECRET_KEY": config.get("LANGFUSE_SECRET_KEY", ""),
        "LANGFUSE_BASE_URL": host,
        "LANGFUSE_HOST": host,
        "LANGFUSE_TRACING_ENVIRONMENT": config.get("LANGFUSE_TRACING_ENVIRONMENT")
        or config.get("LANGFUSE_ENVIRONMENT", ""),
        "LANGFUSE_RELEASE": release,
    }
    for key, value in values.items():
        if value:
            os.environ[key] = str(value)


def openai_langfuse_kwargs(workflow, profile):
    """Return Langfuse-specific OpenAI call kwargs for one workflow."""
    if not langfuse_is_ready():
        return {}

    context = _active_trace_context(workflow)
    metadata = _openai_metadata(workflow, profile, context)
    return {
        "name": _trace_name(workflow),
        "metadata": metadata,
    }


@contextmanager
def langfuse_observation(workflow, profile):
    """Create a Langfuse parent span around one AI workflow when enabled."""
    if not langfuse_is_ready():
        yield {}
        return

    configure_langfuse_environment()
    trace_name = _trace_name(workflow)
    trace_context = _active_trace_context(workflow)
    metadata = {}

    try:
        from langfuse import get_client, propagate_attributes
    except ImportError:
        logger.warning("langfuse_observation_skipped reason=package_missing")
        yield {"langfuse_enabled": False}
        return

    langfuse_client = get_client()

    try:
        with _propagate_langfuse_attributes(
            propagate_attributes,
            trace_context,
            workflow,
            profile,
        ):
            with langfuse_client.start_as_current_observation(
                as_type="span",
                name=trace_name,
                input=_root_span_input(workflow, profile),
            ) as span:

                def _observed_call(callable_):
                    """Run one callable inside the active Langfuse span."""
                    try:
                        result = callable_()
                    except Exception as exc:
                        _mark_span_error(span, exc)
                        raise
                    metadata.update(_current_trace_metadata(langfuse_client))
                    _mark_span_success(span)
                    return result

                yield {"runner": _observed_call, "metadata": metadata}
    except AttributeError:
        logger.warning("langfuse_observation_skipped reason=sdk_context_manager_missing")
        yield {"langfuse_enabled": False}


def normalize_observation_metadata(observation):
    """Return safe diagnostic metadata produced by a Langfuse observation."""
    if not observation or not langfuse_is_ready():
        return {"langfuse_enabled": False}
    if observation.get("langfuse_enabled") is False:
        return {"langfuse_enabled": False}
    metadata = dict(observation.get("metadata") or {})
    metadata.setdefault("langfuse_enabled", True)
    metadata.setdefault("langfuse_host", langfuse_host())
    return metadata


def link_langfuse_answer_trace(diagnostics, chat_message, answer_trace):
    """Attach internal answer trace references to Langfuse without sensitive content."""
    if not langfuse_is_ready():
        return False
    if chat_message is None or answer_trace is None:
        return False
    trace_id = _safe_attribute((diagnostics or {}).get("langfuse_trace_id"))
    if not trace_id:
        return False

    try:
        from langfuse import get_client
    except ImportError:
        logger.warning("langfuse_answer_trace_link_skipped reason=package_missing")
        return False

    metadata = _answer_trace_metadata(chat_message, answer_trace)
    if not metadata:
        return False
    trace_context = {"trace_id": trace_id}
    parent_span_id = _safe_parent_span_id((diagnostics or {}).get("langfuse_observation_id"))
    if parent_span_id:
        trace_context["parent_span_id"] = parent_span_id

    try:
        client = get_client()
        with client.start_as_current_observation(
            as_type="span",
            name="maintenance-ai.answer_trace_link",
            trace_context=trace_context,
            input={"kind": "answer_trace_link"},
        ) as span:
            updater = getattr(span, "update", None)
            if callable(updater):
                updater(metadata=metadata, output={"status": "linked"})
    except AttributeError:
        logger.warning("langfuse_answer_trace_link_skipped reason=sdk_context_manager_missing")
        return False
    except Exception as exc:  # pragma: no cover - external observability guard
        logger.warning("langfuse_answer_trace_link_failed error=%s", exc.__class__.__name__)
        return False
    return True


def _active_trace_context(workflow):
    """Return the active context, falling back to workflow-only metadata."""
    context = _LANGFUSE_CONTEXT.get()
    workflow_value = _safe_attribute(workflow, default="chat")
    if isinstance(context, LangfuseTraceContext):
        return context
    return LangfuseTraceContext(workflow=workflow_value)


def _openai_metadata(workflow, profile, context):
    """Return OpenAI integration metadata consumed by Langfuse."""
    metadata = {
        "workflow": _safe_attribute(workflow, default="chat"),
        "model_tier": _safe_attribute(profile.tier, default="balanced"),
        "model": _safe_attribute(profile.model, default="unknown"),
        "environment": _safe_attribute(
            current_app.config.get("LANGFUSE_TRACING_ENVIRONMENT")
            or current_app.config.get("LANGFUSE_ENVIRONMENT", ""),
        ),
        "release": _release_value(),
        "langfuse_tags": _trace_tags(workflow, profile, context),
    }
    metadata.update(_repository_metadata())
    if context.user_id:
        metadata["langfuse_user_id"] = context.user_id
    if context.user_role:
        metadata["langfuse_user_role"] = context.user_role
    if context.session_id:
        metadata["langfuse_session_id"] = context.session_id
    metadata.update(context.metadata)
    return {key: value for key, value in metadata.items() if value not in ("", [], None)}


@contextmanager
def _propagate_langfuse_attributes(propagate_attributes, context, workflow, profile):
    """Propagate trace attributes to the parent span and child generations."""
    kwargs = {
        "trace_name": _trace_name(workflow),
        "metadata": _propagated_metadata(workflow, profile, context),
        "tags": _trace_tags(workflow, profile, context),
    }
    if context.user_id:
        kwargs["user_id"] = context.user_id
    if context.session_id:
        kwargs["session_id"] = context.session_id
    release = _release_value()
    if release:
        kwargs["version"] = release

    if not any(value for value in kwargs.values()):
        yield
        return

    with propagate_attributes(**kwargs):
        yield


def _propagated_metadata(workflow, profile, context):
    """Return metadata values valid for Langfuse attribute propagation."""
    metadata = {
        "workflow": _safe_attribute(workflow, default="chat"),
        "modeltier": _safe_attribute(profile.tier, default="balanced"),
        "model": _safe_attribute(profile.model, default="unknown"),
        "environment": _safe_attribute(
            current_app.config.get("LANGFUSE_TRACING_ENVIRONMENT")
            or current_app.config.get("LANGFUSE_ENVIRONMENT", ""),
        ),
    }
    metadata.update(_repository_metadata())
    if context.user_role:
        metadata["userrole"] = context.user_role
    metadata.update(context.metadata)
    return _safe_metadata(metadata)


def _repository_metadata():
    """Return GitHub repository metadata for trace filtering without user data."""
    return {
        "repository": _safe_attribute(
            current_app.config.get("GITHUB_REPOSITORY") or os.getenv("GITHUB_REPOSITORY", ""),
        ),
        "commit": _safe_attribute(
            current_app.config.get("GITHUB_SHA") or os.getenv("GITHUB_SHA", ""),
        ),
        "branch": _safe_attribute(
            current_app.config.get("GITHUB_REF_NAME") or os.getenv("GITHUB_REF_NAME", ""),
        ),
    }


def _release_value():
    """Return an explicit Langfuse release or a short GitHub commit value."""
    release = _safe_attribute(current_app.config.get("LANGFUSE_RELEASE", ""))
    if release:
        return release
    return _safe_attribute(current_app.config.get("GITHUB_SHA", ""))[:12]


def _trace_tags(workflow, profile, context):
    """Return filterable Langfuse tags for one workflow."""
    tags = [
        _safe_attribute(workflow, default="chat"),
        _safe_attribute(profile.tier, default="balanced"),
        _safe_attribute(profile.model, default="unknown"),
        *context.tags,
    ]
    return list(dict.fromkeys(tag for tag in tags if tag))


def _root_span_input(workflow, profile):
    """Return intentionally small root span input metadata."""
    return {
        "workflow": _safe_attribute(workflow, default="chat"),
        "model": _safe_attribute(profile.model, default="unknown"),
    }


def _trace_name(workflow):
    """Return a stable trace name for a maintenance AI workflow."""
    return f"maintenance-ai.{_safe_attribute(workflow, default='chat')}"


def _mark_span_success(span):
    """Mark the active Langfuse span as completed without storing response text."""
    updater = getattr(span, "update", None)
    if callable(updater):
        updater(output={"status": "success"})


def _mark_span_error(span, exc):
    """Mark the active Langfuse span as failed without exposing exception details."""
    updater = getattr(span, "update", None)
    if callable(updater):
        updater(
            level="ERROR",
            status_message=exc.__class__.__name__,
            output={"status": "error"},
        )


def _current_trace_metadata(langfuse_client):
    """Return trace identifiers from the active Langfuse context."""
    trace_id = _optional_client_value(langfuse_client, "get_current_trace_id")
    observation_id = _optional_client_value(langfuse_client, "get_current_observation_id")
    metadata = {"langfuse_enabled": True}
    if trace_id:
        metadata["langfuse_trace_id"] = trace_id
    if observation_id:
        metadata["langfuse_observation_id"] = observation_id
    metadata["langfuse_host"] = langfuse_host()
    return metadata


def _optional_client_value(langfuse_client, method_name):
    """Return an optional Langfuse client value without raising instrumentation errors."""
    method = getattr(langfuse_client, method_name, None)
    if not callable(method):
        return None
    try:
        return method()
    except Exception as exc:  # pragma: no cover - SDK compatibility guard
        logger.warning("langfuse_metadata_unavailable method=%s error=%s", method_name, exc)
        return None


def _safe_user_id(user):
    """Return a non-PII Langfuse user identifier."""
    if user is None:
        return ""
    user_id = getattr(user, "id", None)
    if user_id in (None, ""):
        return ""
    return _safe_attribute(f"user:{user_id}")


def _safe_user_role(user):
    """Return a non-PII user role label for Langfuse filtering."""
    role = getattr(user, "role", "")
    role_value = getattr(role, "value", role)
    return _safe_attribute(role_value)


def _safe_session_id(value):
    """Return a Langfuse-compatible optional session identifier."""
    text = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(value or "").strip())
    return text[:MAX_LANGFUSE_ATTRIBUTE_LENGTH]


def _safe_metadata(values):
    """Return metadata with Langfuse-compatible keys and values."""
    safe_values = {}
    for key, value in dict(values).items():
        safe_key = _safe_metadata_key(key)
        safe_value = _safe_attribute(value)
        if safe_key and safe_value:
            safe_values[safe_key[:MAX_LANGFUSE_ATTRIBUTE_LENGTH]] = safe_value
    return safe_values


def _safe_metadata_key(key):
    """Return a Langfuse-safe metadata key or an empty string for sensitive fields."""
    raw_key = str(key or "").strip()
    lowered = raw_key.lower()
    normalized = re.sub(r"[^a-zA-Z0-9]+", "", raw_key)
    normalized_lower = normalized.lower()
    allowed_reference_keys = {
        "answerid",
        "answertraceid",
        "cachedtokens",
        "chatmessageid",
        "confidencescore",
        "inputtokens",
        "outputtokens",
        "totaltokens",
    }
    if normalized_lower in allowed_reference_keys:
        return normalized
    forbidden_parts = (
        "answer",
        "apikey",
        "chunktext",
        "content",
        "filepath",
        "message",
        "password",
        "path",
        "private",
        "prompt",
        "raw",
        "relativepath",
        "response",
        "secret",
        "solution",
        "text",
        "token",
    )
    if any(part in lowered or part in normalized_lower for part in forbidden_parts):
        return ""
    return normalized


def _safe_tags(values):
    """Return safe tag values for Langfuse filtering."""
    for value in values:
        safe_value = _safe_attribute(value)
        if safe_value:
            yield safe_value


def _safe_attribute(value, default=""):
    """Return a compact string accepted by Langfuse attribute propagation."""
    text = " ".join(str(value or default or "").strip().split())
    return text[:MAX_LANGFUSE_ATTRIBUTE_LENGTH]


def _answer_trace_metadata(chat_message, answer_trace):
    """Return sanitized Langfuse metadata linking external traces to internal records."""
    user = getattr(chat_message, "user", None)
    audit_event = _answer_trace_audit_event(answer_trace)
    metadata = {
        "answerid": getattr(answer_trace, "answer_id", ""),
        "answertraceid": getattr(answer_trace, "id", ""),
        "chatmessageid": getattr(chat_message, "id", ""),
        "audit_event_id": getattr(chat_message, "audit_event_id", ""),
        "workflow": getattr(answer_trace, "workflow", ""),
        "model": getattr(answer_trace, "model", ""),
        "modeltier": getattr(answer_trace, "model_tier", ""),
        "sourcecount": getattr(answer_trace, "source_count", ""),
        "chunkcount": getattr(answer_trace, "chunk_count", ""),
        "retrievalused": bool(getattr(answer_trace, "source_count", 0) or 0),
        "inputtokens": getattr(answer_trace, "input_tokens", ""),
        "outputtokens": getattr(answer_trace, "output_tokens", ""),
        "cachedtokens": getattr(answer_trace, "cached_tokens", ""),
        "totaltokens": getattr(answer_trace, "total_tokens", ""),
        "estimatedcostusd": _safe_cost(getattr(answer_trace, "estimated_cost_usd", "")),
        "latencyms": getattr(audit_event, "latency_ms", ""),
        "confidencescore": getattr(answer_trace, "confidence_score", ""),
        "confidencelevel": getattr(answer_trace, "confidence_level", ""),
        "userrole": _safe_user_role(user),
    }
    if getattr(chat_message, "session_id", ""):
        metadata["sessionid"] = _safe_session_id(chat_message.session_id)
    if getattr(chat_message, "user_id", None):
        metadata["userid"] = _safe_attribute(f"user:{chat_message.user_id}")
    return _safe_metadata(metadata)


def _answer_trace_audit_event(answer_trace):
    """Return an optional audit event attached to an answer trace."""
    try:
        return getattr(answer_trace, "audit_event", None)
    except Exception:  # pragma: no cover - defensive lazy-load guard
        return None


def _safe_cost(value):
    """Return a compact cost estimate string for external metadata."""
    try:
        return f"{float(value or 0.0):.6f}"
    except (TypeError, ValueError):
        return "0.000000"


def _safe_parent_span_id(value):
    """Return a valid Langfuse parent observation id when available."""
    text = _safe_attribute(value).lower()
    if re.fullmatch(r"[0-9a-f]{16}", text):
        return text
    return ""


def _eval_io_input(diagnostics, result):
    """Return bounded eval input for Langfuse judges without chunk text."""
    config = current_app.config
    safe_result = result if isinstance(result, dict) else {}
    safe_diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    question = _truncate_eval_text(
        safe_result.get("question") or safe_diagnostics.get("question") or "",
        config.get("LANGFUSE_EVAL_MAX_QUESTION_CHARS", 400),
    )
    answer_quality = safe_result.get("answer_quality") or {}
    if not isinstance(answer_quality, dict):
        answer_quality = {}

    payload = {
        "question": question,
        "guards": {
            "hallucination_warning": bool(safe_diagnostics.get("hallucination_warning")),
            "empty_retrieval": bool(safe_diagnostics.get("empty_retrieval")),
            "status_reason": _safe_attribute(answer_quality.get("status_reason")),
        },
    }
    if config.get("LANGFUSE_EVAL_INCLUDE_SOURCE_TITLES", True):
        payload["context_titles"] = _eval_source_titles(safe_result.get("sources") or [])
    return payload


def _eval_io_output(result):
    """Return bounded eval output for Langfuse judges."""
    safe_result = result if isinstance(result, dict) else {}
    return {
        "answer": _truncate_eval_text(
            safe_result.get("answer") or "",
            current_app.config.get("LANGFUSE_EVAL_MAX_ANSWER_CHARS", 800),
        ),
    }


def _eval_io_metadata(diagnostics, result):
    """Return safe metadata for the eval IO span."""
    safe_result = result if isinstance(result, dict) else {}
    safe_diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    answer_quality = safe_result.get("answer_quality") or {}
    if not isinstance(answer_quality, dict):
        answer_quality = {}
    metadata = {
        "workflow": _safe_attribute(
            safe_diagnostics.get("workflow") or safe_result.get("type"),
        ),
        "answerqualitystatus": _safe_attribute(answer_quality.get("status")),
        "confidencescore": _safe_attribute(_eval_confidence_score(safe_result, safe_diagnostics)),
        "sourcecount": _safe_attribute(
            safe_diagnostics.get("source_count") or len(safe_result.get("sources") or []),
        ),
        "retrievalused": bool(safe_diagnostics.get("retrieval_used")),
    }
    return _safe_metadata(metadata)


def _eval_source_titles(sources):
    """Return prompt-safe source title references for eval IO."""
    titles = []
    for source in sources[:12]:
        if not isinstance(source, dict):
            continue
        titles.append(
            {
                "type": _safe_attribute(source.get("type"), default="source"),
                "title": _safe_attribute(source.get("title"), default="source"),
                "module": _safe_attribute(source.get("module")),
                "machine": _safe_attribute(source.get("machine")),
            }
        )
    return titles


def _eval_confidence_score(result, diagnostics):
    """Return a safe confidence score for eval metadata."""
    confidence = result.get("confidence") or diagnostics.get("confidence") or {}
    if isinstance(confidence, dict) and confidence.get("score") not in (None, ""):
        return confidence.get("score")
    return diagnostics.get("confidence_score")


def _truncate_eval_text(value, max_length):
    """Return eval text truncated to a configured maximum length."""
    text = " ".join(str(value or "").strip().split())
    try:
        limit = int(max_length or 0)
    except (TypeError, ValueError):
        limit = 0
    if limit <= 0:
        return ""
    return text[:limit]


def _langfuse_available():
    """Return whether the Langfuse Python SDK can be imported."""
    try:
        from langfuse import get_client, propagate_attributes  # noqa: F401
        from langfuse.openai import OpenAI as LangfuseOpenAI  # noqa: F401
    except ImportError:
        return False
    return True

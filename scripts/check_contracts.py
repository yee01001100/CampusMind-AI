from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


MODEL_FIELDS: dict[str, set[str]] = {
    "notice": {
        "id",
        "title",
        "raw_text",
        "audience",
        "published_at",
        "deadline",
        "actions",
        "priority",
        "source_type",
        "source_ref",
        "confidence",
        "needs_confirmation",
        "created_at",
    },
    "course": {
        "id",
        "student_id",
        "name",
        "teacher",
        "weekday",
        "start_time",
        "end_time",
        "location",
        "start_week",
        "end_week",
        "week_pattern",
        "custom_weeks",
    },
    "task": {
        "id",
        "student_id",
        "title",
        "description",
        "task_type",
        "priority",
        "status",
        "due_at",
        "source_notice_id",
        "dedupe_key",
        "created_at",
        "completed_at",
    },
    "student_profile": {
        "id",
        "name",
        "major",
        "grade",
        "timezone",
        "quiet_hours_start",
        "quiet_hours_end",
        "interests",
        "reminder_preferences",
    },
    "reminder": {
        "id",
        "task_id",
        "trigger_at",
        "channel",
        "status",
        "sent_at",
        "failure_reason",
    },
}

ENUMS: dict[tuple[str, str], set[str]] = {
    ("notice", "priority"): {"critical", "high", "medium", "normal"},
    ("notice", "source_type"): {"demo", "document", "url", "user_input"},
    ("course", "week_pattern"): {"all", "odd", "even", "custom"},
    ("task", "task_type"): {
        "registration",
        "exam",
        "assignment",
        "course",
        "activity",
        "general",
    },
    ("task", "priority"): {"critical", "high", "medium", "normal"},
    ("task", "status"): {"pending", "completed", "cancelled"},
    ("reminder", "channel"): {"in_app"},
    ("reminder", "status"): {"pending", "sent", "skipped", "failed"},
}

DATETIME_FIELDS: dict[str, tuple[str, ...]] = {
    "notice": ("published_at", "deadline", "created_at"),
    "task": ("due_at", "created_at", "completed_at"),
    "reminder": ("trigger_at", "sent_at"),
}

ERROR_CODES = {
    "VALIDATION_ERROR",
    "STUDENT_NOT_FOUND",
    "NOTICE_EMPTY",
    "NOTICE_DATE_AMBIGUOUS",
    "NOTICE_NOT_APPLICABLE",
    "TASK_DUPLICATE",
    "TASK_NOT_FOUND",
    "COURSE_NOT_FOUND",
    "RAG_NO_SOURCE",
    "AGENT_TOOL_FAILED",
    "MODEL_UNAVAILABLE",
    "INTERNAL_ERROR",
}

API_FIELDS = {"ok", "data", "error", "request_id"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_datetime(
    model_name: str, field: str, value: object, errors: list[str]
) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        errors.append(f"{model_name}.{field} must be an ISO 8601 string or null")
        return
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        errors.append(f"{model_name}.{field} is not valid ISO 8601: {value}")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{model_name}.{field} must include a timezone offset")


def _validate_models(models: object, errors: list[str]) -> None:
    if not isinstance(models, dict):
        errors.append("models.valid.json must contain one JSON object")
        return

    expected_models = set(MODEL_FIELDS)
    actual_models = set(models)
    if actual_models != expected_models:
        errors.append(
            "model example keys differ: "
            f"missing={sorted(expected_models - actual_models)}, "
            f"extra={sorted(actual_models - expected_models)}"
        )

    for model_name, expected_fields in MODEL_FIELDS.items():
        value = models.get(model_name)
        if not isinstance(value, dict):
            errors.append(f"{model_name} example must be an object")
            continue

        actual_fields = set(value)
        if actual_fields != expected_fields:
            errors.append(
                f"{model_name} fields differ: "
                f"missing={sorted(expected_fields - actual_fields)}, "
                f"extra={sorted(actual_fields - expected_fields)}"
            )

        for field in DATETIME_FIELDS.get(model_name, ()):
            _validate_datetime(model_name, field, value.get(field), errors)

        for (enum_model, field), allowed in ENUMS.items():
            if enum_model == model_name and value.get(field) not in allowed:
                errors.append(
                    f"{model_name}.{field} must be one of {sorted(allowed)}"
                )

    notice = models.get("notice", {})
    if isinstance(notice, dict):
        confidence = notice.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append("notice.confidence must be between 0 and 1")
        if notice.get("source_type") != "demo" or "模拟" not in str(
            notice.get("raw_text", "")
        ):
            errors.append("notice example must be visibly marked as demo data")
        if not isinstance(notice.get("audience"), list) or not isinstance(
            notice.get("actions"), list
        ):
            errors.append("notice.audience and notice.actions must be arrays")

    course = models.get("course", {})
    if isinstance(course, dict):
        weekday = course.get("weekday")
        if not isinstance(weekday, int) or not 1 <= weekday <= 7:
            errors.append("course.weekday must be an integer from 1 to 7")
        for field in ("start_time", "end_time"):
            if not isinstance(course.get(field), str) or not TIME_PATTERN.fullmatch(
                str(course.get(field, ""))
            ):
                errors.append(f"course.{field} must use HH:mm")
        if not isinstance(course.get("custom_weeks"), list):
            errors.append("course.custom_weeks must be an array")

    profile = models.get("student_profile", {})
    if isinstance(profile, dict):
        if profile.get("timezone") != "Asia/Shanghai":
            errors.append("student_profile.timezone must be Asia/Shanghai")
        if not isinstance(profile.get("interests"), list) or not isinstance(
            profile.get("reminder_preferences"), dict
        ):
            errors.append(
                "student_profile interests/preferences must be array/object"
            )


def _validate_api_envelope(
    envelope: object, *, success: bool, errors: list[str]
) -> None:
    label = "api.success.json" if success else "api.error.json"
    if not isinstance(envelope, dict):
        errors.append(f"{label} must contain one JSON object")
        return
    if set(envelope) != API_FIELDS:
        errors.append(f"{label} must have exactly {sorted(API_FIELDS)}")
    if envelope.get("ok") is not success:
        errors.append(f"{label}.ok must be {str(success).lower()}")
    if not isinstance(envelope.get("request_id"), str) or not envelope.get(
        "request_id"
    ):
        errors.append(f"{label}.request_id must be a non-empty string")

    if success:
        if envelope.get("error") is not None:
            errors.append("api.success.json.error must be null")
        if not isinstance(envelope.get("data"), dict):
            errors.append("api.success.json.data must be an object")
        return

    if envelope.get("data") is not None:
        errors.append("api.error.json.data must be null")
    error = envelope.get("error")
    if not isinstance(error, dict) or set(error) != {"code", "message", "details"}:
        errors.append("api.error.json.error must contain code/message/details")
        return
    if error.get("code") not in ERROR_CODES:
        errors.append("api.error.json contains an unknown error code")
    if not isinstance(error.get("details"), dict):
        errors.append("api.error.json.error.details must be an object")


def validate_contracts(repo_root: Path | None = None) -> list[str]:
    root = repo_root or Path(__file__).resolve().parents[1]
    examples = root / "contracts" / "examples"
    paths = {
        "models": examples / "models.valid.json",
        "success": examples / "api.success.json",
        "error": examples / "api.error.json",
    }
    errors: list[str] = []

    for label, path in paths.items():
        if not path.is_file():
            errors.append(f"missing contract example: {path.relative_to(root)}")

    if errors:
        return errors

    raw_text = "\n".join(path.read_text(encoding="utf-8") for path in paths.values())
    for pattern in SECRET_PATTERNS:
        if pattern.search(raw_text):
            errors.append("contract examples contain a credential-like value")

    _validate_models(_load_json(paths["models"]), errors)
    _validate_api_envelope(_load_json(paths["success"]), success=True, errors=errors)
    _validate_api_envelope(_load_json(paths["error"]), success=False, errors=errors)
    return errors


def main() -> int:
    errors = validate_contracts()
    if errors:
        print("FAIL: contract examples do not match the frozen Shared Contract")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: 5 model examples and 2 API envelopes match the frozen contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from campusmind.domain import Course, Notice, Reminder, StudentProfile, Task


ROOT = Path(__file__).resolve().parents[2]


def contract_examples() -> dict:
    return json.loads((ROOT / "contracts/examples/models.valid.json").read_text(encoding="utf-8"))


def test_all_five_contract_examples_validate_and_serialize_exact_fields():
    examples = contract_examples()
    models = {
        "notice": Notice,
        "course": Course,
        "task": Task,
        "student_profile": StudentProfile,
        "reminder": Reminder,
    }
    for key, model_type in models.items():
        model = model_type.model_validate(examples[key])
        assert model.model_dump(mode="json") == examples[key]


@pytest.mark.parametrize("field", ["published_at", "deadline", "created_at"])
def test_notice_rejects_naive_datetimes(field: str):
    notice = contract_examples()["notice"]
    notice[field] = "2026-08-18T08:00:00"
    with pytest.raises(ValidationError, match="timezone offset"):
        Notice.model_validate(notice)


def test_low_confidence_notice_requires_confirmation():
    notice = contract_examples()["notice"]
    notice["confidence"] = 0.5
    notice["needs_confirmation"] = False
    with pytest.raises(ValidationError, match="requires confirmation"):
        Notice.model_validate(notice)


def test_course_rejects_bad_time_and_bad_custom_week_contract():
    course = contract_examples()["course"]
    course["end_time"] = "9:30"
    with pytest.raises(ValidationError, match="HH:mm"):
        Course.model_validate(course)

    course = contract_examples()["course"]
    course["week_pattern"] = "custom"
    with pytest.raises(ValidationError, match="requires custom_weeks"):
        Course.model_validate(course)


def test_task_completion_status_and_timestamp_must_agree():
    task = contract_examples()["task"]
    task["status"] = "completed"
    with pytest.raises(ValidationError, match="require completed_at"):
        Task.model_validate(task)

    task = contract_examples()["task"]
    task["completed_at"] = "2026-08-18T09:00:00+08:00"
    with pytest.raises(ValidationError, match="only completed"):
        Task.model_validate(task)


def test_reminder_sent_and_failure_details_are_consistent():
    reminder = contract_examples()["reminder"]
    reminder["status"] = "sent"
    with pytest.raises(ValidationError, match="require sent_at"):
        Reminder.model_validate(reminder)

    reminder = contract_examples()["reminder"]
    reminder["status"] = "failed"
    with pytest.raises(ValidationError, match="require failure_reason"):
        Reminder.model_validate(reminder)


def test_profile_uses_project_timezone_without_system_tzdata():
    profile = StudentProfile.model_validate(contract_examples()["student_profile"])
    assert profile.timezone == "Asia/Shanghai"


def test_contract_models_forbid_second_field_vocabulary():
    task = contract_examples()["task"]
    task["due_date"] = "2026-08-22"
    with pytest.raises(ValidationError, match="Extra inputs"):
        Task.model_validate(task)

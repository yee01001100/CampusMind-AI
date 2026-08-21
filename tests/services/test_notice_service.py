from __future__ import annotations

from datetime import datetime, timezone

import pytest

from campusmind.services.notice import NoticeCandidate, NoticeParseCommand, NoticeService
from campusmind.services.task import ServiceError, TaskService

from .conftest import NOW, ZONE


VALID_NOTICE_CASES = [
    (f"模拟通知{i}：请在 2026年8月{day}日 18:00 前完成事项", f"完成事项{i}")
    for i, day in enumerate(range(20, 30), start=1)
] + [
    (f"模拟通知{i}：请在 2026年9月{day}日 12:30 前完成事项", f"提交材料{i}")
    for i, day in enumerate(range(1, 11), start=11)
]


@pytest.mark.parametrize("text,action", VALID_NOTICE_CASES)
def test_twenty_notice_validation_samples(repository, text: str, action: str) -> None:
    service = NoticeService(repository, TaskService(repository))
    result = service.parse(
        NoticeParseCommand(
            text=text,
            student_id="student-demo-001",
            reference_time=NOW,
            candidate=NoticeCandidate(actions=[action], confidence=0.95),
        )
    )

    assert result.notice.raw_text == text
    assert result.notice.deadline is not None
    assert result.notice.deadline.utcoffset().total_seconds() == 8 * 3600
    assert result.notice.needs_confirmation is False
    assert [task.title for task in result.tasks] == [action]


@pytest.mark.parametrize(
    "text,expected_code",
    [
        ("请在8月22日完成报名", "NOTICE_DATE_AMBIGUOUS"),
        ("请在12月1日提交材料", "NOTICE_DATE_AMBIGUOUS"),
        ("截止时间为2月28日", "NOTICE_DATE_AMBIGUOUS"),
        ("请在2026年2月30日完成", "VALIDATION_ERROR"),
        ("请在2026年13月1日完成", "VALIDATION_ERROR"),
    ],
)
def test_five_ambiguous_or_invalid_dates(repository, text: str, expected_code: str) -> None:
    service = NoticeService(repository, TaskService(repository))
    with pytest.raises(ServiceError) as captured:
        service.parse(
            NoticeParseCommand(
                text=text,
                student_id="student-demo-001",
                reference_time=NOW,
            )
        )
    assert captured.value.code == expected_code


def test_empty_notice_is_stable_error(repository) -> None:
    with pytest.raises(ServiceError) as captured:
        NoticeService(repository, TaskService(repository)).parse(
            NoticeParseCommand(text="  ", student_id="student-demo-001", reference_time=NOW)
        )
    assert captured.value.code == "NOTICE_EMPTY"


def test_relative_friday_and_multiple_actions(repository) -> None:
    result = NoticeService(repository, TaskService(repository)).parse(
        NoticeParseCommand(
            text="本周五 18:00 截止，要求：完成报名；提交承诺书",
            student_id="student-demo-001",
            reference_time=NOW,
            candidate=NoticeCandidate(confidence=0.9),
        )
    )
    assert result.notice.deadline == datetime(2026, 8, 21, 18, 0, tzinfo=ZONE)
    assert result.notice.actions == ["完成报名", "提交承诺书"]
    assert len(result.tasks) == 2


def test_relative_weekday_normalizes_utc_reference_to_shanghai(repository) -> None:
    result = NoticeService(repository, TaskService(repository)).parse(
        NoticeParseCommand(
            text="本周五 18:00 截止，要求：提交材料",
            student_id="student-demo-001",
            reference_time=datetime(2026, 8, 16, 16, 30, tzinfo=timezone.utc),
            candidate=NoticeCandidate(confidence=0.9),
        )
    )

    assert result.notice.deadline == datetime(2026, 8, 21, 18, 0, tzinfo=ZONE)
    assert result.notice.created_at == datetime(2026, 8, 17, 0, 30, tzinfo=ZONE)
    assert result.expired is False


def test_registration_start_and_deadline_create_distinct_actions(repository) -> None:
    result = NoticeService(repository, TaskService(repository)).parse(
        NoticeParseCommand(
            text="报名开始后请处理，报名截止为 2026年8月25日 17:00",
            student_id="student-demo-001",
            reference_time=NOW,
            candidate=NoticeCandidate(
                actions=["查看报名资格", "完成报名"], confidence=0.98
            ),
        )
    )
    assert {task.title for task in result.tasks} == {"查看报名资格", "完成报名"}
    assert all(task.task_type == "registration" for task in result.tasks)


def test_not_applicable_audience_rejected(repository) -> None:
    service = NoticeService(repository, TaskService(repository))
    with pytest.raises(ServiceError) as captured:
        service.parse(
            NoticeParseCommand(
                text="2026级本科生请在 2026年8月25日 18:00 报名",
                student_id="student-demo-001",
                student_segments=["2025级本科生"],
                reference_time=NOW,
            )
        )
    assert captured.value.code == "NOTICE_NOT_APPLICABLE"


def test_expired_notice_is_recorded_without_tasks(repository) -> None:
    result = NoticeService(repository, TaskService(repository)).parse(
        NoticeParseCommand(
            text="过期演示：请于 2026年8月17日 12:00 报名",
            student_id="student-demo-001",
            reference_time=NOW,
        )
    )
    assert result.expired is True
    assert result.notice.priority == "critical"
    assert result.tasks == []


def test_duplicate_notice_returns_existing_without_new_tasks(repository) -> None:
    service = NoticeService(repository, TaskService(repository))
    command = NoticeParseCommand(
        text="唯一通知：2026年8月25日 18:00 报名",
        student_id="student-demo-001",
        reference_time=NOW,
        candidate=NoticeCandidate(source_ref="demo://notice/unique", confidence=0.9),
    )
    first = service.parse(command)
    second = service.parse(command)
    assert first.duplicate is False
    assert second.duplicate is True
    assert second.notice.id == first.notice.id
    assert [task.id for task in second.tasks] == [task.id for task in first.tasks]


def test_low_confidence_requires_confirmation_and_creates_no_task(repository) -> None:
    result = NoticeService(repository, TaskService(repository)).parse(
        NoticeParseCommand(
            text="不确定通知，没有明确日期",
            student_id="student-demo-001",
            reference_time=NOW,
            candidate=NoticeCandidate(confidence=0.6),
        )
    )
    assert result.notice.needs_confirmation is True
    assert result.tasks == []

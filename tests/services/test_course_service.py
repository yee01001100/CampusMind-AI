from __future__ import annotations

from datetime import date, datetime

import pytest

from campusmind.services.course import Course, CourseService, TimeBlock

from .conftest import ZONE


COURSE_QUERY_CASES = [
    (date(2026, 8, 17), 1, "all", [], True),
    (date(2026, 8, 18), 2, "all", [], True),
    (date(2026, 8, 19), 3, "odd", [], True),
    (date(2026, 8, 26), 3, "odd", [], False),
    (date(2026, 8, 27), 4, "even", [], True),
    (date(2026, 8, 20), 4, "even", [], False),
    (date(2026, 8, 21), 5, "custom", [1, 3], True),
    (date(2026, 8, 28), 5, "custom", [1, 3], False),
    (date(2026, 8, 16), 7, "all", [], False),
    (date(2026, 8, 24), 1, "all", [], True),
]


@pytest.mark.parametrize("day,weekday,pattern,custom,expected", COURSE_QUERY_CASES)
def test_ten_course_query_groups(repository, day, weekday, pattern, custom, expected) -> None:
    repository.save_course(
        Course(
            id="course-case",
            student_id="student-demo-001",
            name="测试课程",
            weekday=weekday,
            start_time="09:00",
            end_time="10:00",
            start_week=1,
            end_week=16,
            week_pattern=pattern,
            custom_weeks=custom,
        )
    )
    result = CourseService(repository).for_day("student-demo-001", day)
    assert bool(result.courses) is expected


@pytest.mark.parametrize(
    "left,right,overlap",
    [
        ((9, 0, 10, 0), (9, 30, 10, 30), 30),
        ((8, 0, 12, 0), (9, 0, 10, 0), 60),
        ((13, 0, 14, 30), (14, 0, 15, 0), 30),
        ((18, 0, 20, 0), (19, 45, 21, 0), 15),
        ((7, 30, 8, 30), (7, 45, 8, 0), 15),
    ],
)
def test_five_conflict_groups(left, right, overlap) -> None:
    def block(block_id: str, values: tuple[int, int, int, int]) -> TimeBlock:
        sh, sm, eh, em = values
        return TimeBlock(
            id=block_id,
            title=block_id,
            kind="course" if block_id == "left" else "exam",
            start_at=datetime(2026, 8, 18, sh, sm, tzinfo=ZONE),
            end_at=datetime(2026, 8, 18, eh, em, tzinfo=ZONE),
        )

    conflicts = CourseService.detect_conflicts([block("left", left), block("right", right)])
    assert len(conflicts) == 1
    assert conflicts[0].overlap_minutes == overlap


def test_touching_blocks_are_not_conflict() -> None:
    blocks = [
        TimeBlock(
            id="a", title="A", kind="course",
            start_at=datetime(2026, 8, 18, 9, tzinfo=ZONE),
            end_at=datetime(2026, 8, 18, 10, tzinfo=ZONE),
        ),
        TimeBlock(
            id="b", title="B", kind="task",
            start_at=datetime(2026, 8, 18, 10, tzinfo=ZONE),
            end_at=datetime(2026, 8, 18, 11, tzinfo=ZONE),
        ),
    ]
    assert CourseService.detect_conflicts(blocks) == []


def test_next_course_free_time_and_empty_state(repository) -> None:
    for course_id, start, end in (("one", "09:00", "10:00"), ("two", "11:30", "12:30")):
        repository.save_course(
            Course(
                id=course_id,
                student_id="student-demo-001",
                name=course_id,
                weekday=2,
                start_time=start,
                end_time=end,
                start_week=1,
                end_week=16,
            )
        )
    result = CourseService(repository).for_day(
        "student-demo-001",
        date(2026, 8, 18),
        now=datetime(2026, 8, 18, 10, 30, tzinfo=ZONE),
    )
    assert result.next_course.id == "two"
    assert result.free_slots[0].minutes == 90
    empty = CourseService(repository).for_day("student-demo-001", date(2026, 8, 19))
    assert empty.courses == []
    assert empty.next_course is None

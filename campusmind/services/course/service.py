from __future__ import annotations

from datetime import date, datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

from .models import Course, CourseConflict, CourseDayResult, FreeSlot, TimeBlock


class CourseRepository(Protocol):
    def list_courses(self, student_id: str) -> list[Course]: ...


class CourseService:
    def __init__(
        self,
        repository: CourseRepository,
        *,
        term_start: date = date(2026, 8, 17),
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self.repository = repository
        self.term_start = term_start
        self.timezone = ZoneInfo(timezone)

    def week_for(self, day: date) -> int | None:
        delta = (day - self.term_start).days
        return None if delta < 0 else delta // 7 + 1

    @staticmethod
    def occurs(course: Course, *, day: date, week: int | None) -> bool:
        if week is None or day.isoweekday() != course.weekday:
            return False
        if not course.start_week <= week <= course.end_week:
            return False
        if course.week_pattern == "odd":
            return week % 2 == 1
        if course.week_pattern == "even":
            return week % 2 == 0
        if course.week_pattern == "custom":
            return week in course.custom_weeks
        return True

    def for_day(self, student_id: str, day: date, *, now: datetime | None = None) -> CourseDayResult:
        week = self.week_for(day)
        courses = sorted(
            [
                course
                for course in self.repository.list_courses(student_id)
                if self.occurs(course, day=day, week=week)
            ],
            key=lambda course: course.start_time,
        )
        compare_at = now or datetime.combine(day, time.min, tzinfo=self.timezone)
        next_course = next(
            (
                course
                for course in courses
                if datetime.combine(
                    day, datetime.strptime(course.start_time, "%H:%M").time(), tzinfo=self.timezone
                )
                >= compare_at
            ),
            None,
        )
        return CourseDayResult(
            date=day,
            week=week,
            courses=courses,
            next_course=next_course,
            free_slots=self.free_time(courses, day),
        )

    def free_time(self, courses: list[Course], day: date) -> list[FreeSlot]:
        ordered = sorted(courses, key=lambda course: course.start_time)
        slots: list[FreeSlot] = []
        for left, right in zip(ordered, ordered[1:]):
            start_at = datetime.combine(
                day, datetime.strptime(left.end_time, "%H:%M").time(), tzinfo=self.timezone
            )
            end_at = datetime.combine(
                day, datetime.strptime(right.start_time, "%H:%M").time(), tzinfo=self.timezone
            )
            if end_at > start_at:
                slots.append(
                    FreeSlot(
                        start_at=start_at,
                        end_at=end_at,
                        minutes=int((end_at - start_at).total_seconds() // 60),
                    )
                )
        return slots

    @staticmethod
    def detect_conflicts(blocks: list[TimeBlock]) -> list[CourseConflict]:
        conflicts: list[CourseConflict] = []
        ordered = sorted(blocks, key=lambda block: block.start_at)
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                if right.start_at >= left.end_at:
                    break
                overlap = min(left.end_at, right.end_at) - max(left.start_at, right.start_at)
                if overlap.total_seconds() > 0:
                    conflicts.append(
                        CourseConflict(
                            left_id=left.id,
                            right_id=right.id,
                            overlap_minutes=int(overlap.total_seconds() // 60),
                        )
                    )
        return conflicts

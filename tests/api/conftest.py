from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from apps.api.fakes import InMemoryRepository
from apps.api.main import create_app
from campusmind.services.course import Course
from campusmind.services.reminder import StudentProfile

ZONE = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 18, 8, 0, tzinfo=ZONE)


@pytest.fixture
def api_repository() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.save_profile(
        StudentProfile(
            id="student-demo-001",
            name="模拟学生",
            grade="2026",
            quiet_hours_start="23:00",
            quiet_hours_end="07:00",
        )
    )
    repo.save_course(
        Course(
            id="course-demo-001",
            student_id="student-demo-001",
            name="人工智能导论",
            weekday=2,
            start_time="10:00",
            end_time="11:35",
            start_week=1,
            end_week=16,
        )
    )
    return repo


@pytest.fixture
def client(api_repository: InMemoryRepository) -> TestClient:
    return TestClient(create_app(repository=api_repository, clock=lambda: NOW))

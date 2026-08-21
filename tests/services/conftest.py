from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apps.api.fakes import InMemoryRepository
from campusmind.services.reminder import StudentProfile
from campusmind.services.task import TaskService

ZONE = ZoneInfo("Asia/Shanghai")
NOW = datetime(2026, 8, 18, 8, 0, tzinfo=ZONE)


@pytest.fixture
def repository() -> InMemoryRepository:
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
    return repo


@pytest.fixture
def task_service(repository: InMemoryRepository) -> TaskService:
    return TaskService(repository)

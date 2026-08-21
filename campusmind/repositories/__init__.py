"""Stable repository imports for CampusMind services and tests."""

from .rag import (
    KnowledgeDocument,
    KnowledgeImporter,
    RAGMatch,
    RAGNoSourceError,
    RAGRetriever,
    RAGSource,
)
from .sqlite import (
    CourseRepository,
    NoticeRepository,
    ReminderRepository,
    StudentProfileRepository,
    TaskRepository,
)

__all__ = [
    "CourseRepository",
    "KnowledgeDocument",
    "KnowledgeImporter",
    "NoticeRepository",
    "RAGMatch",
    "RAGNoSourceError",
    "RAGRetriever",
    "RAGSource",
    "ReminderRepository",
    "StudentProfileRepository",
    "TaskRepository",
]

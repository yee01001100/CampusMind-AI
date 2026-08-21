from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from campusmind.repositories import (
    KnowledgeDocument,
    KnowledgeImporter,
    RAGNoSourceError,
    RAGRetriever,
)
from campusmind.storage import SQLiteDatabase


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "data/knowledge"


def knowledge_database(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "knowledge.sqlite3")
    database.initialize()
    KnowledgeImporter(database).import_directory(KNOWLEDGE)
    return database


def test_knowledge_corpus_has_required_categories_and_metadata():
    documents = [
        KnowledgeDocument.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(KNOWLEDGE.glob("*.json"))
    ]
    categories = [document.source_type for document in documents]
    assert len(documents) == 10
    assert categories.count("academic_rule") == 2
    assert categories.count("campus_notice") == 5
    assert categories.count("registration_guide") == 1
    assert categories.count("exam_rule") == 1
    assert categories.count("scholarship_guide") == 1
    assert all(document.is_demo is True for document in documents)
    assert all(document.source_ref.startswith("demo://") for document in documents)


def test_import_is_repeatable_without_duplicate_sources_or_chunks(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "repeat-rag.sqlite3")
    database.initialize()
    importer = KnowledgeImporter(database)
    first = importer.import_directory(KNOWLEDGE)
    second = importer.import_directory(KNOWLEDGE)
    assert (first.imported, first.updated, first.unchanged) == (10, 0, 0)
    assert (second.imported, second.updated, second.unchanged) == (0, 0, 10)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM rag_sources").fetchone()[0] == 10
        chunks = connection.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]
        assert chunks >= 10


def test_search_returns_snippet_and_complete_source_metadata(tmp_path: Path):
    retriever = RAGRetriever(knowledge_database(tmp_path))
    matches = retriever.search("四六级报名截止时间", as_of=date(2026, 8, 21))
    assert matches
    first = matches[0]
    assert "2026年8月22日18:00" in first.snippet
    assert first.source.source_id == "knowledge-demo-cet-001"
    assert first.source.title == "模拟大学英语四六级报名说明"
    assert first.source.source_ref == "demo://knowledge/cet-registration"
    assert first.source.is_demo is True
    assert first.source.effective_date == date(2026, 8, 18)
    assert first.source.is_expired is False


def test_empty_database_returns_rag_no_source_instead_of_fabrication(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "empty-rag.sqlite3")
    database.initialize()
    with pytest.raises(RAGNoSourceError) as caught:
        RAGRetriever(database).search("学校的正式毕业规定", as_of=date(2026, 8, 21))
    assert caught.value.code == "RAG_NO_SOURCE"
    assert str(caught.value) == "知识库没有可靠来源"


@pytest.mark.parametrize("query", ["", "   ", "火星停车许可证办理地点"])
def test_empty_or_unknown_query_returns_rag_no_source(tmp_path: Path, query: str):
    retriever = RAGRetriever(knowledge_database(tmp_path))
    with pytest.raises(RAGNoSourceError) as caught:
        retriever.search(query, as_of=date(2026, 8, 21))
    assert caught.value.code == "RAG_NO_SOURCE"


def test_expired_source_is_excluded_by_default_but_retains_validity_when_requested(tmp_path: Path):
    retriever = RAGRetriever(knowledge_database(tmp_path))
    with pytest.raises(RAGNoSourceError):
        retriever.search("旧版缓考申请材料", as_of=date(2026, 8, 21))
    match = retriever.search(
        "旧版缓考申请材料", as_of=date(2026, 8, 21), include_expired=True
    )[0]
    assert match.source.source_id == "knowledge-demo-academic-002"
    assert match.source.effective_date == date(2025, 9, 1)
    assert match.source.expires_at == date(2026, 7, 31)
    assert match.source.is_expired is True


def test_future_effective_source_is_not_returned(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "future.sqlite3")
    database.initialize()
    KnowledgeImporter(database).import_document(
        KnowledgeDocument(
            source_id="future-source", title="未来模拟规定", source_type="academic_rule",
            published_at="2027-01-01T08:00:00+08:00", effective_date="2027-02-01",
            expires_at=None, source_ref="demo://knowledge/future", is_demo=True,
            content="未来模拟规定包含量子课程报名规则。",
        )
    )
    with pytest.raises(RAGNoSourceError):
        RAGRetriever(database).search("量子课程报名", as_of=date(2026, 8, 21))


def test_reimport_changed_document_replaces_old_chunks(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "update.sqlite3")
    database.initialize()
    importer = KnowledgeImporter(database)
    original = KnowledgeDocument(
        source_id="replace-source", title="模拟替换资料", source_type="campus_notice",
        published_at="2026-08-01T08:00:00+08:00", effective_date="2026-08-01",
        expires_at=None, source_ref="demo://knowledge/replace", is_demo=True,
        content="旧内容提到蓝色凭证。",
    )
    assert importer.import_document(original) == "imported"
    updated = original.model_copy(update={"content": "新内容改为绿色凭证。"})
    assert importer.import_document(updated) == "updated"
    retriever = RAGRetriever(database)
    assert "绿色凭证" in retriever.search("绿色凭证", as_of=date(2026, 8, 21))[0].snippet
    with pytest.raises(RAGNoSourceError):
        retriever.search("旧内容提到", as_of=date(2026, 8, 21))
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM rag_chunks WHERE source_id='replace-source'"
        ).fetchone()[0] == 1


def test_knowledge_metadata_rejects_naive_time_and_invalid_validity():
    payload = json.loads((KNOWLEDGE / "exam-management.json").read_text(encoding="utf-8"))
    payload["published_at"] = "2026-08-01T10:00:00"
    with pytest.raises(ValidationError, match="timezone offset"):
        KnowledgeDocument.model_validate(payload)

    payload = json.loads((KNOWLEDGE / "exam-management.json").read_text(encoding="utf-8"))
    payload["expires_at"] = "2026-07-01"
    with pytest.raises(ValidationError, match="must not precede"):
        KnowledgeDocument.model_validate(payload)


def test_search_limit_must_be_positive(tmp_path: Path):
    retriever = RAGRetriever(knowledge_database(tmp_path))
    with pytest.raises(ValueError, match="at least 1"):
        retriever.search("考试", as_of=date(2026, 8, 21), limit=0)

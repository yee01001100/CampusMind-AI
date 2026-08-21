"""Deterministic local knowledge import and source-backed lexical retrieval."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from campusmind.storage.database import SQLiteDatabase


class KnowledgeDocument(BaseModel):
    """On-disk knowledge document with the required provenance fields."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    published_at: datetime
    effective_date: date
    expires_at: date | None = None
    source_ref: str = Field(min_length=1)
    is_demo: bool
    content: str = Field(min_length=1)

    @field_validator("published_at")
    @classmethod
    def published_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must include a timezone offset")
        return value

    @model_validator(mode="after")
    def validity_is_ordered(self) -> "KnowledgeDocument":
        if self.expires_at is not None and self.expires_at < self.effective_date:
            raise ValueError("expires_at must not precede effective_date")
        return self


class RAGSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    source_type: str
    published_at: datetime
    effective_date: date
    expires_at: date | None
    source_ref: str
    is_demo: bool
    is_expired: bool


class RAGMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snippet: str
    score: float = Field(gt=0)
    source: RAGSource


class RAGNoSourceError(LookupError):
    code = "RAG_NO_SOURCE"

    def __init__(self, query: str):
        self.query = query
        super().__init__("知识库没有可靠来源")


@dataclass(frozen=True)
class ImportResult:
    imported: int = 0
    updated: int = 0
    unchanged: int = 0


def _chunks(content: str, max_chars: int = 420) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    result: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            result.append(paragraph)
            continue
        start = 0
        while start < len(paragraph):
            result.append(paragraph[start : start + max_chars].strip())
            start += max_chars - 60
    return result


def _tokens(text: str) -> set[str]:
    lowered = text.casefold()
    ascii_tokens = set(re.findall(r"[a-z0-9]+", lowered))
    chinese_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    chinese_tokens: set[str] = set()
    for run in chinese_runs:
        if len(run) == 1:
            chinese_tokens.add(run)
        else:
            chinese_tokens.update(run[index : index + 2] for index in range(len(run) - 1))
    return ascii_tokens | chinese_tokens


class KnowledgeImporter:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def import_directory(self, directory: str | Path) -> ImportResult:
        path = Path(directory)
        if not path.is_dir():
            raise FileNotFoundError(path)
        imported = updated = unchanged = 0
        for file_path in sorted(path.glob("*.json")):
            document = KnowledgeDocument.model_validate_json(file_path.read_text(encoding="utf-8"))
            state = self.import_document(document)
            if state == "imported":
                imported += 1
            elif state == "updated":
                updated += 1
            else:
                unchanged += 1
        return ImportResult(imported=imported, updated=updated, unchanged=unchanged)

    def import_document(self, document: KnowledgeDocument) -> str:
        payload = document.model_dump(mode="json")
        content_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        chunks = _chunks(document.content)
        if not chunks:
            raise ValueError("knowledge document produced no searchable chunks")
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT content_hash FROM rag_sources WHERE source_id = ?",
                (document.source_id,),
            ).fetchone()
            if row is not None and row["content_hash"] == content_hash:
                return "unchanged"
            state = "updated" if row is not None else "imported"
            connection.execute(
                """
                INSERT INTO rag_sources
                    (source_id, title, source_type, published_at, effective_date,
                     expires_at, source_ref, is_demo, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    title=excluded.title, source_type=excluded.source_type,
                    published_at=excluded.published_at,
                    effective_date=excluded.effective_date,
                    expires_at=excluded.expires_at, source_ref=excluded.source_ref,
                    is_demo=excluded.is_demo, content_hash=excluded.content_hash
                """,
                (
                    document.source_id, document.title, document.source_type,
                    document.published_at.isoformat(), document.effective_date.isoformat(),
                    document.expires_at.isoformat() if document.expires_at else None,
                    document.source_ref, int(document.is_demo), content_hash,
                ),
            )
            connection.execute("DELETE FROM rag_chunks WHERE source_id = ?", (document.source_id,))
            connection.executemany(
                """
                INSERT INTO rag_chunks(source_id, position, content, search_text)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (document.source_id, position, chunk, chunk.casefold())
                    for position, chunk in enumerate(chunks)
                ],
            )
            connection.commit()
        return state


class RAGRetriever:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def search(
        self,
        query: str,
        *,
        as_of: date | None = None,
        limit: int = 3,
        include_expired: bool = False,
    ) -> list[RAGMatch]:
        query = query.strip()
        if not query:
            raise RAGNoSourceError(query)
        if limit < 1:
            raise ValueError("limit must be at least 1")
        as_of = as_of or date.today()
        query_tokens = _tokens(query)
        if not query_tokens:
            raise RAGNoSourceError(query)

        sql = """
            SELECT c.content, s.*
            FROM rag_chunks c
            JOIN rag_sources s ON s.source_id = c.source_id
            WHERE s.effective_date <= ?
        """
        params: list[str] = [as_of.isoformat()]
        if not include_expired:
            sql += " AND (s.expires_at IS NULL OR s.expires_at >= ?)"
            params.append(as_of.isoformat())
        with self.database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()

        ranked: list[tuple[float, str, object]] = []
        normalized_query = query.casefold()
        for row in rows:
            content_tokens = _tokens(row["content"])
            title_tokens = _tokens(row["title"])
            overlap = query_tokens & content_tokens
            title_overlap = query_tokens & title_tokens
            exact_match = normalized_query in row["content"].casefold()
            content_coverage = len(overlap) / len(query_tokens)
            title_coverage = len(title_overlap) / len(query_tokens)
            # One generic bigram such as "地点" is not reliable evidence. A
            # result needs at least half of the query phrase, a strong title
            # match, or the complete query as a substring.
            if not exact_match and max(content_coverage, title_coverage) < 0.5:
                continue
            score = content_coverage + title_coverage
            if exact_match:
                score += 0.5
            ranked.append((score, row["source_id"], row))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        matches: list[RAGMatch] = []
        seen_sources: set[str] = set()
        for score, source_id, row in ranked:
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            expires_at = date.fromisoformat(row["expires_at"]) if row["expires_at"] else None
            source = RAGSource(
                source_id=source_id,
                title=row["title"],
                source_type=row["source_type"],
                published_at=row["published_at"],
                effective_date=row["effective_date"],
                expires_at=expires_at,
                source_ref=row["source_ref"],
                is_demo=bool(row["is_demo"]),
                is_expired=expires_at is not None and expires_at < as_of,
            )
            matches.append(RAGMatch(snippet=row["content"][:320], score=score, source=source))
            if len(matches) >= limit:
                break
        if not matches:
            raise RAGNoSourceError(query)
        return matches

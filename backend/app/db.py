import json
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import JSON, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

ENRICH_SCHEMAS = ("kho_a", "kho_b", "thu_thap")  # phân hệ làm giàu dữ liệu MST — app/models_enrich.py


class Base(DeclarativeBase):
    pass


class EmbeddingVector(TypeDecorator):
    """Vector embedding: cột pgvector `vector(dim)` trên PostgreSQL, JSON (danh sách số) trên SQLite khi test."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 1024):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import VECTOR

            return dialect.type_descriptor(VECTOR(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        return None if value is None else [float(x) for x in value]

    def process_result_value(self, value, dialect):
        return None if value is None else [float(x) for x in value]


def utcnow() -> datetime:
    """Thời điểm hiện tại theo UTC, dạng naive (lưu giống nhau trên SQLite và PostgreSQL)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _json_dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False)


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    # JSON lưu chữ Việt nguyên dạng (không thoát kiểu \\u00ec) để lọc "chứa" trên cột JSON (vd ngành nghề) tìm được
    kwargs: dict = {"pool_pre_ping": True, "json_serializer": _json_dumps}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # SQLite không có schema: bỏ tên schema kho_a/kho_b/thu_thap (tên bảng đã duy nhất nhờ tiền tố enrich_)
        return create_engine(url, **kwargs).execution_options(schema_translate_map=dict.fromkeys(ENRICH_SCHEMAS))
    return create_engine(url, **kwargs)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def new_session() -> Session:
    return _session_factory()()


def get_db() -> Iterator[Session]:
    db = new_session()
    try:
        yield db
    finally:
        db.close()

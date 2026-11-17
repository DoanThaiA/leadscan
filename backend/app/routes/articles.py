"""Cẩm nang (blog SEO): API công khai /api/articles/* và API quản trị /api/admin/articles/*.

Bài hiện công khai khi status = "published" và published_at ≤ hiện tại (đặt ngày tương lai = hẹn giờ đăng).
Ảnh bìa dùng chung luồng tải ảnh của tuyển dụng (services/job_covers) với thư mục riêng article-covers/.
"""

import math
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import current_user, require_admin
from app.db import get_db, utcnow
from app.models import ARTICLE_CATEGORIES, ARTICLE_STATUSES, AdminUser, Article
from app.schemas import Line
from app.schemas_jobs import CoverInitIn, clean_cover, slugify
from app.services import job_covers
from app.services.storage import StorageError

public = APIRouter(prefix="/api/articles")
admin = APIRouter(prefix="/api/admin/articles")

COVER_PREFIX = "article-covers"
COVER_PATH = "/api/articles/covers"
DEFAULT_AUTHOR = "LeadScan"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def reading_minutes(body: str) -> int:
    return max(1, math.ceil(len(re.findall(r"\w+", body)) / 220))


def _visible():
    return (Article.status == "published", Article.published_at.is_not(None), Article.published_at <= utcnow())


def card_out(a: Article) -> dict:
    return {
        "slug": a.slug, "title": a.title, "excerpt": a.excerpt, "category": a.category, "area": a.area, "cover_image": a.cover_image,
        "published_at": _iso(a.published_at), "updated_at": _iso(a.updated_at), "reading_minutes": reading_minutes(a.body),
    }


def full_out(a: Article) -> dict:
    return {**card_out(a), "seo_title": a.seo_title, "body": a.body, "author_name": a.author_name or DEFAULT_AUTHOR}


# ================================================================== công khai


@public.get("")
def list_articles(category: str = "", areas: str = Query("", max_length=300), page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=60), db: Session = Depends(get_db)):
    stmt = select(Article).where(*_visible())
    if category:
        stmt = stmt.where(Article.category == category)
    area_list = [x.strip() for x in areas.split(",") if x.strip()][:10]  # trang khu vực: "bac-ninh,mien-bac" = bài của tỉnh và của miền
    if area_list:
        stmt = stmt.where(Article.area.in_(area_list))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Article.published_at.desc(), Article.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    counts = dict(db.execute(select(Article.category, func.count()).where(*_visible()).group_by(Article.category)).all())
    area_counts = {k: n for k, n in db.execute(select(Article.area, func.count()).where(*_visible()).group_by(Article.area)).all() if k}
    return {
        "total": total, "page": page, "page_size": page_size, "items": [card_out(a) for a in rows],
        "area_counts": area_counts, "categories": [[c, counts.get(c, 0)] for c in ARTICLE_CATEGORIES] + [[c, n] for c, n in counts.items() if c and c not in ARTICLE_CATEGORIES],
    }


@public.get("/covers/{name}")
def cover(name: str):
    try:
        data = job_covers.read_cover(name, prefix=COVER_PREFIX)
    except StorageError:
        raise HTTPException(502, "Kho lưu trữ tạm thời lỗi.") from None
    return Response(data, media_type="image/webp", headers={
        "Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'",
    })


@public.get("/{slug}")
def get_article(slug: str, db: Session = Depends(get_db)):
    a = db.scalar(select(Article).where(Article.slug == slug, *_visible()))
    if not a:
        raise HTTPException(404, "Không tìm thấy bài viết.")
    # Bài liên quan: cùng khu vực trước, rồi cùng chủ đề, rồi bài mới nhất — tối đa 3, không trùng
    related: list[Article] = []
    for cond in ([Article.area == a.area] if a.area else []) + ([Article.category == a.category] if a.category else []) + [None]:
        if len(related) >= 3:
            break
        stmt = select(Article).where(*_visible(), Article.id != a.id, Article.id.not_in([r.id for r in related] or [0]))
        if cond is not None:
            stmt = stmt.where(cond)
        related += db.scalars(stmt.order_by(Article.published_at.desc()).limit(3 - len(related))).all()
    return {**full_out(a), "related": [card_out(r) for r in related]}


# ================================================================== quản trị


class ArticleIn(BaseModel):
    title: Line = Field(min_length=5, max_length=200)
    slug: str = Field("", max_length=160)  # trống = tự sinh từ tiêu đề
    status: str = "draft"
    seo_title: Line = Field("", max_length=200)
    excerpt: Line = Field("", max_length=400)
    category: Line = Field("", max_length=80)
    area: str = Field("", max_length=60)  # slug khu vực, trống = bài chung
    cover_image: str = Field("", max_length=500)
    body: str = Field("", max_length=100_000)
    author_name: Line = Field("", max_length=120)
    published_at: datetime | None = None  # trống + đăng = đăng ngay; ngày tương lai = hẹn giờ

    @field_validator("cover_image")
    @classmethod
    def _cover(cls, v: str) -> str:
        return clean_cover(v)  # cùng quy tắc ảnh bìa với tuyển dụng

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        return slugify(v)

    @field_validator("area")
    @classmethod
    def _area(cls, v: str) -> str:
        v = v.strip()
        if v and slugify(v) != v:
            raise ValueError("Khu vực không hợp lệ.")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in ARTICLE_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        return v

    @field_validator("published_at")
    @classmethod
    def _naive_utc(cls, v: datetime | None) -> datetime | None:
        if v and v.tzinfo:
            v = v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


def admin_out(a: Article) -> dict:
    return {
        **full_out(a), "id": a.id, "status": a.status, "author_name": a.author_name,
        "published_at": _iso(a.published_at), "created_at": _iso(a.created_at), "updated_at": _iso(a.updated_at),
        "is_live": a.status == "published" and bool(a.published_at) and a.published_at <= utcnow(),
    }


def unique_slug(db: Session, wanted: str, title: str, exclude_id: int | None = None) -> str:
    base = wanted or slugify(title) or "bai-viet"
    slug, n = base, 2
    while True:
        stmt = select(Article.id).where(Article.slug == slug)
        if exclude_id:
            stmt = stmt.where(Article.id != exclude_id)
        if not db.scalar(stmt):
            return slug
        slug, n = f"{base}-{n}", n + 1


def apply(db: Session, a: Article, body: ArticleIn) -> None:
    data = body.model_dump()
    data["slug"] = unique_slug(db, data["slug"], data["title"], exclude_id=a.id)
    if not data["published_at"]:
        data["published_at"] = a.published_at  # giữ ngày đăng cũ khi form để trống
    for f, v in data.items():
        setattr(a, f, v)
    if a.status == "published" and not a.published_at:
        a.published_at = utcnow()


def _get(db: Session, aid: int) -> Article:
    a = db.get(Article, aid)
    if not a:
        raise HTTPException(404, "Không tìm thấy bài viết.")
    return a


@admin.get("/meta")
def meta(_: AdminUser = Depends(current_user)):
    return {"statuses": ARTICLE_STATUSES, "categories": ARTICLE_CATEGORIES}


@admin.post("/covers/init", status_code=201)
def cover_init(body: CoverInitIn, _: AdminUser = Depends(current_user)):
    return job_covers.init_upload(body.filename, body.size, prefix=COVER_PREFIX)


@admin.post("/covers/{upload_id}/complete")
def cover_complete(upload_id: str, _: AdminUser = Depends(current_user)):
    return job_covers.complete_upload(upload_id, prefix=COVER_PREFIX, public_path=COVER_PATH)


@admin.get("")
def admin_list(status: str = "", q: str = Query("", max_length=100), _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Article)
    if status:
        stmt = stmt.where(Article.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Article.title.ilike(like), Article.slug.ilike(like.replace(" ", "-"))))
    rows = db.scalars(stmt.order_by(Article.updated_at.desc(), Article.id.desc()).limit(300)).all()
    counts = dict(db.execute(select(Article.status, func.count()).group_by(Article.status)).all())
    return {"items": [{k: v for k, v in admin_out(a).items() if k != "body"} for a in rows], "counts": counts}


@admin.post("", status_code=201)
def admin_create(body: ArticleIn, user: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    a = Article(created_by_id=user.id)
    apply(db, a, body)
    db.add(a)
    db.commit()
    db.refresh(a)
    return admin_out(a)


@admin.get("/{aid}")
def admin_get(aid: int, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    return admin_out(_get(db, aid))


@admin.put("/{aid}")
def admin_update(aid: int, body: ArticleIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    a = _get(db, aid)
    apply(db, a, body)
    db.commit()
    db.refresh(a)
    return admin_out(a)


@admin.delete("/{aid}", status_code=204)
def admin_delete(aid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    db.delete(_get(db, aid))
    db.commit()
    return Response(status_code=204)

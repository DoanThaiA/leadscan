"""Bài viết theo danh mục (Cẩm nang, Tuyển dụng, Tin tức…): API công khai /api/articles/*,
API quản trị /api/admin/articles/* (bài) và /api/admin/article-sections/* (danh mục).

Bài hiện công khai khi status = "published", published_at ≤ hiện tại (đặt ngày tương lai = hẹn giờ đăng) và danh mục đang bật.
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
from app.models import ARTICLE_CATEGORIES, ARTICLE_STATUSES, DEFAULT_SECTION_SLUG, AdminUser, Article, ArticleSection
from app.schemas import Line
from app.schemas_jobs import CoverInitIn, clean_cover, slugify
from app.services import job_covers
from app.services.storage import StorageError

public = APIRouter(prefix="/api/articles")
admin = APIRouter(prefix="/api/admin/articles")
sections_admin = APIRouter(prefix="/api/admin/article-sections")

COVER_PREFIX = "article-covers"
COVER_PATH = "/api/articles/covers"
DEFAULT_AUTHOR = "LeadScan"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def reading_minutes(body: str) -> int:
    return max(1, math.ceil(len(re.findall(r"\w+", body)) / 220))


def _visible():
    return (
        Article.status == "published", Article.published_at.is_not(None), Article.published_at <= utcnow(),
        Article.section_id.in_(select(ArticleSection.id).where(ArticleSection.is_active.is_(True))),
    )


def default_section(db: Session) -> ArticleSection:
    """Danh mục Cẩm nang — tạo nếu chưa có (DB mới / test). Bài không chọn danh mục rơi vào đây."""
    sec = db.scalar(select(ArticleSection).where(ArticleSection.slug == DEFAULT_SECTION_SLUG))
    if not sec:
        sec = ArticleSection(slug=DEFAULT_SECTION_SLUG, name="Cẩm nang", sort_order=1)
        db.add(sec)
        db.flush()
    return sec


def card_out(a: Article) -> dict:
    return {
        "slug": a.slug, "title": a.title, "excerpt": a.excerpt, "category": a.category, "area": a.area, "cover_image": a.cover_image,
        "section": a.section.slug if a.section else DEFAULT_SECTION_SLUG, "section_name": a.section.name if a.section else "Cẩm nang",
        "published_at": _iso(a.published_at), "updated_at": _iso(a.updated_at), "reading_minutes": reading_minutes(a.body),
    }


def section_out(sec: ArticleSection) -> dict:
    return {"id": sec.id, "slug": sec.slug, "name": sec.name, "description": sec.description, "sort_order": sec.sort_order, "is_active": sec.is_active}


def full_out(a: Article) -> dict:
    return {**card_out(a), "seo_title": a.seo_title, "body": a.body, "author_name": a.author_name or DEFAULT_AUTHOR}


# ================================================================== công khai


@public.get("")
def list_articles(
    section: str = Query("", max_length=80), category: str = "", areas: str = Query("", max_length=300),
    page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=60), db: Session = Depends(get_db),
):
    """section = slug danh mục (trống = mọi danh mục, dùng cho sitemap). Đếm chủ đề / khu vực trong phạm vi danh mục đó."""
    scope = list(_visible())
    if section:
        scope.append(Article.section_id.in_(select(ArticleSection.id).where(ArticleSection.slug == section)))
    stmt = select(Article).where(*scope)
    if category:
        stmt = stmt.where(Article.category == category)
    area_list = [x.strip() for x in areas.split(",") if x.strip()][:10]  # trang khu vực: "bac-ninh,mien-bac" = bài của tỉnh và của miền
    if area_list:
        stmt = stmt.where(Article.area.in_(area_list))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Article.published_at.desc(), Article.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    counts = dict(db.execute(select(Article.category, func.count()).where(*scope).group_by(Article.category)).all())
    area_counts = {k: n for k, n in db.execute(select(Article.area, func.count()).where(*scope).group_by(Article.area)).all() if k}
    preset = ARTICLE_CATEGORIES if section in ("", DEFAULT_SECTION_SLUG) else []  # chủ đề gợi ý chỉ dành cho Cẩm nang
    return {
        "total": total, "page": page, "page_size": page_size, "items": [card_out(a) for a in rows],
        "area_counts": area_counts, "categories": [[c, counts.get(c, 0)] for c in preset] + [[c, n] for c, n in counts.items() if c and c not in preset],
    }


@public.get("/sections")
def list_sections(db: Session = Depends(get_db)):
    """Danh mục đang bật + số bài đang hiện (trang /bai-viet, sitemap)."""
    counts = dict(db.execute(select(Article.section_id, func.count()).where(*_visible()).group_by(Article.section_id)).all())
    rows = db.scalars(select(ArticleSection).where(ArticleSection.is_active.is_(True)).order_by(ArticleSection.sort_order, ArticleSection.id)).all()
    return {"items": [{"slug": x.slug, "name": x.name, "description": x.description, "count": counts.get(x.id, 0)} for x in rows]}


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
    # Bài liên quan (cùng danh mục): cùng khu vực trước, rồi cùng chủ đề, rồi bài mới nhất — tối đa 3, không trùng
    related: list[Article] = []
    for cond in ([Article.area == a.area] if a.area else []) + ([Article.category == a.category] if a.category else []) + [None]:
        if len(related) >= 3:
            break
        stmt = select(Article).where(*_visible(), Article.section_id == a.section_id, Article.id != a.id, Article.id.not_in([r.id for r in related] or [0]))
        if cond is not None:
            stmt = stmt.where(cond)
        related += db.scalars(stmt.order_by(Article.published_at.desc()).limit(3 - len(related))).all()
    return {**full_out(a), "related": [card_out(r) for r in related]}


# ================================================================== quản trị


class ArticleIn(BaseModel):
    title: Line = Field(min_length=5, max_length=200)
    slug: str = Field("", max_length=160)  # trống = tự sinh từ tiêu đề
    section_id: int | None = None  # danh mục; trống = giữ danh mục cũ / Cẩm nang
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
        **full_out(a), "id": a.id, "section_id": a.section_id, "status": a.status, "author_name": a.author_name,
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
    if data["section_id"] is None:
        data["section_id"] = a.section_id or default_section(db).id
    elif not db.get(ArticleSection, data["section_id"]):
        raise HTTPException(422, "Danh mục không tồn tại.")
    data["slug"] = unique_slug(db, data["slug"], data["title"], exclude_id=a.id)
    if not data["published_at"]:
        data["published_at"] = a.published_at  # giữ ngày đăng cũ khi form để trống
    for f, v in data.items():
        setattr(a, f, v)
    a.section = db.get(ArticleSection, a.section_id)  # trả về đúng danh mục mới ngay sau khi lưu
    if a.status == "published" and not a.published_at:
        a.published_at = utcnow()


def _get(db: Session, aid: int) -> Article:
    a = db.get(Article, aid)
    if not a:
        raise HTTPException(404, "Không tìm thấy bài viết.")
    return a


def _sections(db: Session) -> list[ArticleSection]:
    default_section(db)
    return list(db.scalars(select(ArticleSection).order_by(ArticleSection.sort_order, ArticleSection.id)).all())


@admin.get("/meta")
def meta(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    secs = _sections(db)
    db.commit()
    # Chủ đề gợi ý theo danh mục: Cẩm nang có bộ chủ đề sẵn; danh mục nào cũng thêm các chủ đề đã dùng
    used: dict[int, set[str]] = {}
    for sid, cat in db.execute(select(Article.section_id, Article.category).where(Article.category != "").distinct()).all():
        used.setdefault(sid, set()).add(cat)
    topics = {
        str(x.id): (ARTICLE_CATEGORIES if x.slug == DEFAULT_SECTION_SLUG else []) + sorted(used.get(x.id, set()) - set(ARTICLE_CATEGORIES))
        for x in secs
    }
    return {"statuses": ARTICLE_STATUSES, "categories": ARTICLE_CATEGORIES, "sections": [section_out(x) for x in secs], "topics": topics}


@admin.post("/covers/init", status_code=201)
def cover_init(body: CoverInitIn, _: AdminUser = Depends(current_user)):
    return job_covers.init_upload(body.filename, body.size, prefix=COVER_PREFIX)


@admin.post("/covers/{upload_id}/complete")
def cover_complete(upload_id: str, _: AdminUser = Depends(current_user)):
    return job_covers.complete_upload(upload_id, prefix=COVER_PREFIX, public_path=COVER_PATH)


@admin.get("")
def admin_list(
    status: str = "", section_id: int | None = None, q: str = Query("", max_length=100),
    _: AdminUser = Depends(current_user), db: Session = Depends(get_db),
):
    in_section = [Article.section_id == section_id] if section_id else []
    stmt = select(Article).where(*in_section)
    if status:
        stmt = stmt.where(Article.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Article.title.ilike(like), Article.slug.ilike(like.replace(" ", "-"))))
    rows = db.scalars(stmt.order_by(Article.updated_at.desc(), Article.id.desc()).limit(300)).all()
    counts = dict(db.execute(select(Article.status, func.count()).where(*in_section).group_by(Article.status)).all())
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


# ================================================================== quản trị: danh mục


class SectionIn(BaseModel):
    name: Line = Field(min_length=2, max_length=100)
    slug: str = Field("", max_length=80)  # chỉ dùng khi tạo; trống = tự sinh từ tên
    description: Line = Field("", max_length=400)
    sort_order: int = Field(0, ge=0, le=9999)
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        return slugify(v)[:80]


def _section(db: Session, sid: int) -> ArticleSection:
    sec = db.get(ArticleSection, sid)
    if not sec:
        raise HTTPException(404, "Không tìm thấy danh mục.")
    return sec


def _section_admin_out(db: Session, secs: list[ArticleSection]) -> list[dict]:
    counts: dict[int, dict[str, int]] = {}
    for sid, st, n in db.execute(select(Article.section_id, Article.status, func.count()).group_by(Article.section_id, Article.status)).all():
        counts.setdefault(sid, {})[st] = n
    live = dict(db.execute(select(Article.section_id, func.count()).where(*_visible()).group_by(Article.section_id)).all())
    return [
        {**section_out(x), "counts": counts.get(x.id, {}), "total": sum(counts.get(x.id, {}).values()), "live": live.get(x.id, 0),
         "is_default": x.slug == DEFAULT_SECTION_SLUG, "created_at": _iso(x.created_at), "updated_at": _iso(x.updated_at)}
        for x in secs
    ]


@sections_admin.get("")
def sections_list(_: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    secs = _sections(db)
    db.commit()
    return {"items": _section_admin_out(db, secs)}


@sections_admin.post("", status_code=201)
def sections_create(body: SectionIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    slug = body.slug or slugify(body.name)[:80]
    if not slug:
        raise HTTPException(422, "Tên danh mục cần có chữ hoặc số.")
    if db.scalar(select(ArticleSection.id).where(ArticleSection.slug == slug)):
        raise HTTPException(409, f"Đường dẫn “{slug}” đã được dùng, hãy đặt đường dẫn khác.")
    sec = ArticleSection(slug=slug, name=body.name, description=body.description, sort_order=body.sort_order, is_active=body.is_active)
    db.add(sec)
    db.commit()
    db.refresh(sec)
    return _section_admin_out(db, [sec])[0]


@sections_admin.put("/{sid}")
def sections_update(sid: int, body: SectionIn, _: AdminUser = Depends(current_user), db: Session = Depends(get_db)):
    sec = _section(db, sid)
    if sec.slug == DEFAULT_SECTION_SLUG and not body.is_active:
        raise HTTPException(409, "Không ẩn được danh mục Cẩm nang (trang /cam-nang). Muốn ẩn bài, hãy chuyển bài về Bản nháp.")
    # slug giữ nguyên: đổi slug = gãy mọi link bài đã chia sẻ / Google đã lập chỉ mục
    sec.name, sec.description, sec.sort_order, sec.is_active = body.name, body.description, body.sort_order, body.is_active
    db.commit()
    db.refresh(sec)
    return _section_admin_out(db, [sec])[0]


@sections_admin.delete("/{sid}", status_code=204)
def sections_delete(sid: int, _: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    sec = _section(db, sid)
    if sec.slug == DEFAULT_SECTION_SLUG:
        raise HTTPException(409, "Không xoá được danh mục Cẩm nang.")
    n = db.scalar(select(func.count()).select_from(Article).where(Article.section_id == sid)) or 0
    if n:
        raise HTTPException(409, f"Danh mục còn {n} bài viết. Chuyển các bài sang danh mục khác hoặc xoá bài trước.")
    db.delete(sec)
    db.commit()
    return Response(status_code=204)

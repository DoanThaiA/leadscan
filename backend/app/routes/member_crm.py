"""API CRM Lite cho thành viên hạng Vàng: /api/member/crm/*

Mọi truy vấn lọc theo company_id của thành viên đang đăng nhập — lead của doanh nghiệp khác trả 404.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db, utcnow
from app.member_auth import current_member
from app.models import MemberUser
from app.models_crm import CRM_STAGES, CrmEvent, CrmLead, CrmNote, CrmTask
from app.services import crm, crm_ai, crm_export

router = APIRouter(prefix="/api/member/crm")


def crm_member(user: MemberUser = Depends(current_member)) -> MemberUser:
    ok, why = crm.access(user.company)
    if not ok:
        raise HTTPException(403, why)
    return user


def _lead(db: Session, user: MemberUser, lead_id: int) -> CrmLead:
    lead = db.scalar(select(CrmLead).where(CrmLead.id == lead_id, CrmLead.company_id == user.company_id))
    if not lead:
        raise HTTPException(404, "Không tìm thấy lead.")
    return lead


def _teammate(db: Session, user: MemberUser, member_id: int | None) -> MemberUser | None:
    if member_id is None:
        return None
    m = db.scalar(select(MemberUser).where(MemberUser.id == member_id, MemberUser.company_id == user.company_id, MemberUser.is_active.is_(True)))
    if not m:
        raise HTTPException(422, "Người được giao không thuộc doanh nghiệp của bạn.")
    return m


def _members(db: Session, user: MemberUser) -> list[dict]:
    rows = db.scalars(select(MemberUser).where(MemberUser.company_id == user.company_id, MemberUser.is_active.is_(True)).order_by(MemberUser.full_name))
    return [{"id": m.id, "full_name": m.full_name} for m in rows]


# ================================================================== bảng pipeline


def _overdue_count(db: Session, cond: list, stats: dict) -> int:
    """Số lead (trong bộ lọc đang xem) có việc quá hạn."""
    ids = [lid for lid, (_, due) in stats.items() if due and due < date.today()]
    return db.scalar(select(func.count(CrmLead.id)).where(*cond, CrmLead.id.in_(ids))) or 0 if ids else 0


@router.get("/board")
def board(
    owner: str = Query("all", pattern="^(all|me)$"),
    q: str = Query("", max_length=100),
    per_stage: int = Query(50, ge=1, le=1000),  # số thẻ mỗi cột (mới cập nhật trước) — 10.000 lead không gửi hết một lần
    user: MemberUser = Depends(crm_member),
    db: Session = Depends(get_db),
):
    crm.sync_leads(db, user.company_id)
    cond = [CrmLead.company_id == user.company_id]
    if owner == "me":
        cond.append(CrmLead.owner_id == user.id)
    stats = crm.task_stats(db, user.company_id)
    if q.strip():  # tìm trong mã / tiêu đề / bên có nhu cầu của bản đã mua (lưu JSON nên lọc sau khi đọc), không giới hạn cột
        needle = q.strip().lower()
        rows = db.scalars(select(CrmLead).where(*cond).order_by(CrmLead.updated_at.desc())).unique()
        leads = [x for x in (crm.lead_out(lead, stats.get(lead.id)) for lead in rows) if needle in f"{x['code']} {x['title']} {x['buyer_name']}".lower()]
        counts = {k: sum(1 for x in leads if x["stage"] == k) for k in CRM_STAGES}
    else:
        rn = func.row_number().over(partition_by=CrmLead.stage, order_by=(CrmLead.updated_at.desc(), CrmLead.id.desc())).label("rn")
        top = select(CrmLead.id, rn).where(*cond).subquery()
        rows = db.scalars(
            select(CrmLead).where(CrmLead.id.in_(select(top.c.id).where(top.c.rn <= per_stage))).order_by(CrmLead.updated_at.desc(), CrmLead.id.desc())
        ).unique()
        leads = [crm.lead_out(lead, stats.get(lead.id)) for lead in rows]
        counts = dict(db.execute(select(CrmLead.stage, func.count(CrmLead.id)).where(*cond).group_by(CrmLead.stage)).all())
    return {
        "stages": [{"key": k, "label": v} for k, v in CRM_STAGES.items()],
        "leads": leads,
        "counts": {k: counts.get(k, 0) for k in CRM_STAGES},
        "total": sum(counts.values()),
        "overdue": _overdue_count(db, cond, stats),
        "per_stage": per_stage,
        "members": _members(db, user),
        "me": user.id,
    }


# ================================================================== chi tiết lead


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    lead = _lead(db, user, lead_id)
    stats = crm.task_stats(db, user.company_id)
    notes = db.scalars(select(CrmNote).where(CrmNote.lead_id == lead.id).order_by(CrmNote.id.desc())).unique()
    tasks = db.scalars(select(CrmTask).where(CrmTask.lead_id == lead.id).order_by(CrmTask.done_at.is_not(None), CrmTask.due_date.is_(None), CrmTask.due_date, CrmTask.id)).unique()
    events = db.scalars(select(CrmEvent).where(CrmEvent.lead_id == lead.id).order_by(CrmEvent.id.desc()).limit(100)).unique()
    return {
        "lead": crm.lead_out(lead, stats.get(lead.id)),
        "opportunity": crm.snapshot(lead),
        "notes": [crm.note_out(n) for n in notes],
        "tasks": [crm.task_out(t) for t in tasks],
        "events": [crm.event_out(e) for e in events],
        "stages": [{"key": k, "label": v} for k, v in CRM_STAGES.items()],
        "members": _members(db, user),
        "ai": {
            "budget": crm_ai.budget_out(db, user.company_id),
            "summary": crm_ai.run_out(crm_ai.latest(db, lead.id, "summary")),
            "draft": crm_ai.run_out(crm_ai.latest(db, lead.id, "draft")),
        },
    }


# ================================================================== trợ lý AI (bản nháp — người dùng tự sửa, tự gửi)


class DraftIn(BaseModel):
    channel: str = Field("email", pattern="^(email|zalo|call)$")
    note: str = Field("", max_length=1000)  # ý chính muốn nói (SĐT/email trong đây bị che trước khi gửi AI)


@router.post("/leads/{lead_id}/ai/summary")
def ai_summary(lead_id: int, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    r = crm_ai.run(db, _lead(db, user, lead_id), user, "summary")
    return {"run": crm_ai.run_out(r), "budget": crm_ai.budget_out(db, user.company_id)}


@router.post("/leads/{lead_id}/ai/draft")
def ai_draft(lead_id: int, body: DraftIn, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    r = crm_ai.run(db, _lead(db, user, lead_id), user, "draft", body.channel, body.note)
    return {"run": crm_ai.run_out(r), "budget": crm_ai.budget_out(db, user.company_id)}


@router.get("/ai/budget")
def ai_budget(user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    return crm_ai.budget_out(db, user.company_id)


# ================================================================== xuất Excel (chỉ dữ liệu doanh nghiệp)


@router.get("/export.xlsx")
def export_xlsx(user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    crm.sync_leads(db, user.company_id)
    leads = db.scalars(select(CrmLead).where(CrmLead.company_id == user.company_id).order_by(CrmLead.id)).unique().all()
    data = crm_export.leads_xlsx(leads, crm.task_stats(db, user.company_id))
    name = f"leadscan-crm-{date.today().isoformat()}.xlsx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


class LeadPatch(BaseModel):
    stage: str | None = None
    owner_id: int | None = None
    unassign: bool = False  # bỏ người phụ trách (owner_id=None không phân biệt được với "không đổi")

    @field_validator("stage")
    @classmethod
    def _stage(cls, v):
        if v is not None and v not in CRM_STAGES:
            raise ValueError("Giai đoạn không hợp lệ.")
        return v


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, body: LeadPatch, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    lead = _lead(db, user, lead_id)
    if body.stage and body.stage != lead.stage:
        crm.log(db, lead, user, "stage", f"{CRM_STAGES[lead.stage]} → {CRM_STAGES[body.stage]}")
        lead.stage = body.stage
    if body.unassign and lead.owner_id is not None:
        crm.log(db, lead, user, "assign", "Bỏ người phụ trách")
        lead.owner_id = None
    elif body.owner_id is not None and body.owner_id != lead.owner_id:
        m = _teammate(db, user, body.owner_id)
        crm.log(db, lead, user, "assign", f"Giao cho {m.full_name}")
        lead.owner_id = m.id
    db.commit()
    db.refresh(lead)
    return crm.lead_out(lead, crm.task_stats(db, user.company_id).get(lead.id))


# ================================================================== ghi chú


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


@router.post("/leads/{lead_id}/notes", status_code=201)
def add_note(lead_id: int, body: NoteIn, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    lead = _lead(db, user, lead_id)
    text = body.content.strip()
    if not text:
        raise HTTPException(422, "Ghi chú đang trống.")
    text, masked = crm.mask_pii(text, crm.snapshot(lead))
    note = CrmNote(company_id=user.company_id, lead_id=lead.id, author_id=user.id, content=text)
    db.add(note)
    crm.log(db, lead, user, "note", text[:200])
    db.commit()
    db.refresh(note)
    return {
        "note": crm.note_out(note),
        "masked": masked,
        "warning": f"Đã ẩn {masked} SĐT/email không thuộc đầu mối của phiếu — CRM không lưu thêm dữ liệu cá nhân." if masked else "",
    }


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    note = db.scalar(select(CrmNote).where(CrmNote.id == note_id, CrmNote.company_id == user.company_id))
    if not note:
        raise HTTPException(404, "Không tìm thấy ghi chú.")
    if note.author_id != user.id:
        raise HTTPException(403, "Chỉ người viết mới xoá được ghi chú.")
    db.delete(note)
    db.commit()


# ================================================================== việc cần làm


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    assignee_id: int | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    due_date: date | None = None
    clear_due: bool = False
    assignee_id: int | None = None
    done: bool | None = None


@router.post("/leads/{lead_id}/tasks", status_code=201)
def add_task(lead_id: int, body: TaskIn, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    lead = _lead(db, user, lead_id)
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "Tên việc đang trống.")
    who = _teammate(db, user, body.assignee_id) or user
    t = CrmTask(company_id=user.company_id, lead_id=lead.id, title=title, due_date=body.due_date, assignee_id=who.id, created_by_id=user.id)
    db.add(t)
    due = f" (hạn {body.due_date.strftime('%d/%m/%Y')})" if body.due_date else ""
    crm.log(db, lead, user, "task", f"Thêm việc: {title}{due}")
    db.commit()
    db.refresh(t)
    return crm.task_out(t)


def _task(db: Session, user: MemberUser, task_id: int) -> CrmTask:
    t = db.scalar(select(CrmTask).where(CrmTask.id == task_id, CrmTask.company_id == user.company_id))
    if not t:
        raise HTTPException(404, "Không tìm thấy việc.")
    return t


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, body: TaskPatch, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    t = _task(db, user, task_id)
    if body.title is not None and body.title.strip():
        t.title = body.title.strip()
    if body.clear_due:
        t.due_date = None
    elif body.due_date is not None:
        t.due_date = body.due_date
    if body.assignee_id is not None:
        t.assignee_id = _teammate(db, user, body.assignee_id).id
    if body.done is True and not t.done_at:
        t.done_at = utcnow()
        crm.log(db, t.lead, user, "task_done", f"Xong việc: {t.title}")
    elif body.done is False and t.done_at:
        t.done_at = None
        crm.log(db, t.lead, user, "task", f"Mở lại việc: {t.title}")
    db.commit()
    db.refresh(t)
    return crm.task_out(t)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, user: MemberUser = Depends(crm_member), db: Session = Depends(get_db)):
    t = _task(db, user, task_id)
    crm.log(db, t.lead, user, "task", f"Xoá việc: {t.title}")
    db.delete(t)
    db.commit()


@router.get("/tasks")
def list_tasks(
    scope: str = Query("mine", pattern="^(mine|all)$"),
    status: str = Query("open", pattern="^(open|done)$"),
    user: MemberUser = Depends(crm_member),
    db: Session = Depends(get_db),
):
    crm.sync_leads(db, user.company_id)
    stmt = select(CrmTask).where(CrmTask.company_id == user.company_id)
    if scope == "mine":
        stmt = stmt.where(or_(CrmTask.assignee_id == user.id, CrmTask.assignee_id.is_(None)))
    if status == "open":
        stmt = stmt.where(CrmTask.done_at.is_(None)).order_by(CrmTask.due_date.is_(None), CrmTask.due_date, CrmTask.id).limit(500)
    else:
        stmt = stmt.where(CrmTask.done_at.is_not(None)).order_by(CrmTask.done_at.desc()).limit(200)
    items = [crm.task_out(t, with_lead=True) for t in db.scalars(stmt).unique()]
    today = date.today().isoformat()
    return {
        "items": items,
        "counts": {
            "overdue": sum(1 for x in items if x["overdue"]),
            "today": sum(1 for x in items if not x["done"] and x["due_date"] == today),
        },
    }

"""Email CRM Lite cho hạng Vàng: nhắc việc 8:00 hằng ngày và báo cáo tuần sáng thứ Hai (lịch trong app/worker.py).

Nhắc việc gửi riêng từng người: việc của họ quá hạn / hạn hôm nay / hạn ngày mai, và lead họ phụ trách lâu chưa chạm.
Không có gì cần nhắc thì không gửi. Báo cáo tuần gửi mọi thành viên của doanh nghiệp có lead.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Company, MemberUser
from app.models_crm import CRM_STAGES, CrmEvent, CrmLead, CrmTask
from app.services import crm, notify

VN = ZoneInfo("Asia/Ho_Chi_Minh")
STALE_DAYS = 7  # lead đang mở bao lâu không có hoạt động thì nhắc
OPEN_STAGES = ("new", "contacting", "interested", "quoted")


def vn_today() -> date:
    return datetime.now(VN).date()


def _crm_url(cfg: Settings) -> str:
    return cfg.member_url.rstrip("/") + "/crm"


def gold_companies(db: Session, cfg: Settings) -> list[Company]:
    """Doanh nghiệp hạng Vàng đã có lead trong CRM."""
    ids = db.scalars(select(CrmLead.company_id).distinct()).all()
    rows = db.scalars(select(Company).where(Company.id.in_(ids))).unique().all() if ids else []
    return [c for c in rows if crm.access(c, cfg)[0] and c.status not in ("suspended", "rejected")]


def _members(db: Session, company_id: int) -> list[MemberUser]:
    return list(db.scalars(select(MemberUser).where(MemberUser.company_id == company_id, MemberUser.is_active.is_(True))).unique())


def _fmt(d: date) -> str:
    return d.strftime("%d/%m")


# ------------------------------------------------------------------ nhắc việc hằng ngày


def daily_for(db: Session, m: MemberUser, today: date) -> dict:
    tomorrow = today + timedelta(days=1)
    tasks = db.scalars(
        select(CrmTask)
        .join(CrmLead, CrmLead.id == CrmTask.lead_id)
        .where(
            CrmTask.company_id == m.company_id,
            CrmTask.done_at.is_(None),
            CrmTask.due_date.is_not(None),
            CrmTask.due_date <= tomorrow,
            or_(CrmTask.assignee_id == m.id, (CrmTask.assignee_id.is_(None)) & (CrmLead.owner_id == m.id)),
        )
        .order_by(CrmTask.due_date, CrmTask.id)
    ).unique().all()
    cutoff = datetime.now(VN).replace(tzinfo=None) - timedelta(days=STALE_DAYS)  # updated_at lưu UTC — lệch vài giờ không quan trọng
    stale = db.scalars(
        select(CrmLead)
        .where(CrmLead.company_id == m.company_id, CrmLead.owner_id == m.id, CrmLead.stage.in_(OPEN_STAGES), CrmLead.updated_at < cutoff)
        .order_by(CrmLead.updated_at)
        .limit(10)
    ).unique().all()
    return {
        "overdue": [t for t in tasks if t.due_date < today],
        "today": [t for t in tasks if t.due_date == today],
        "tomorrow": [t for t in tasks if t.due_date == tomorrow],
        "stale": stale,
    }


def daily_body(cfg: Settings, m: MemberUser, d: dict, name: str = "", shared: bool = False) -> tuple[str, str] | None:
    """name: tên người nhận (người liên hệ của khách); shared: doanh nghiệp có nhiều tài khoản → ghi rõ việc của ai."""
    if not any(d.values()):
        return None
    base = _crm_url(cfg)
    whose = f" (tài khoản {m.full_name})" if shared else ""
    lines = [f"Chào {name or m.full_name},", "", f"Việc cần làm hôm nay trong CRM LeadScan{whose}:", ""]

    def task_lines(title: str, items: list[CrmTask]):
        if not items:
            return
        lines.append(f"{title} ({len(items)})")
        for t in items[:15]:
            s = crm.snapshot(t.lead)
            lines.append(f"  • {t.title} — hạn {_fmt(t.due_date)} · {s.get('code', '')} {s.get('title', '')[:70]}")
            lines.append(f"    {base}/{t.lead_id}")
        if len(items) > 15:
            lines.append(f"  … và {len(items) - 15} việc khác")
        lines.append("")

    task_lines("QUÁ HẠN", d["overdue"])
    task_lines("HẠN HÔM NAY", d["today"])
    task_lines("HẠN NGÀY MAI", d["tomorrow"])
    if d["stale"]:
        lines.append(f"LEAD LÂU CHƯA CHẠM (trên {STALE_DAYS} ngày không có hoạt động)")
        for lead in d["stale"]:
            s = crm.snapshot(lead)
            lines.append(f"  • {s.get('code', '')} {s.get('title', '')[:80]} — {CRM_STAGES.get(lead.stage, lead.stage)}")
            lines.append(f"    {base}/{lead.id}")
        lines.append("")
    lines += [f"Tất cả việc của bạn: {base}/viec", "", "Trân trọng,", "Đội ngũ LeadScan"]
    n = len(d["overdue"]) + len(d["today"])
    subject = f"[LeadScan CRM] {n} việc cần làm hôm nay" + (f", {len(d['overdue'])} quá hạn" if d["overdue"] else "") if n else "[LeadScan CRM] Lead cần chăm sóc"
    return subject, "\n".join(lines) + "\n"


def send_daily(db: Session, cfg: Settings | None = None, today: date | None = None) -> int:
    cfg = cfg or get_settings()
    today = today or vn_today()
    sent = 0
    for c in gold_companies(db, cfg):
        to = notify.company_contact(db, c.id)  # gửi người liên hệ của khách, không gửi email đăng nhập
        if not to:
            continue
        members = _members(db, c.id)
        for m in members:
            mail = daily_body(cfg, m, daily_for(db, m, today), to[1], shared=len(members) > 1)
            if mail and notify.send_mail(cfg, mail[0], mail[1], to=to[0]):
                sent += 1
    return sent


# ------------------------------------------------------------------ báo cáo tuần (thứ Hai)


def weekly_for(db: Session, company_id: int, today: date) -> dict:
    since = datetime.combine(today - timedelta(days=7), datetime.min.time())
    by_stage = dict(db.execute(select(CrmLead.stage, func.count(CrmLead.id)).where(CrmLead.company_id == company_id).group_by(CrmLead.stage)).all())
    ev = db.execute(select(CrmEvent.kind, CrmEvent.content).where(CrmEvent.company_id == company_id, CrmEvent.created_at >= since)).all()
    return {
        "by_stage": by_stage,
        "new_leads": sum(1 for k, _ in ev if k == "created"),
        "won": sum(1 for k, c in ev if k == "stage" and c.endswith(f"→ {CRM_STAGES['won']}")),
        "lost": sum(1 for k, c in ev if k == "stage" and c.endswith(f"→ {CRM_STAGES['lost']}")),
        "tasks_done": sum(1 for k, _ in ev if k == "task_done"),
        "notes": sum(1 for k, _ in ev if k == "note"),
        "overdue": db.scalar(select(func.count(CrmTask.id)).where(CrmTask.company_id == company_id, CrmTask.done_at.is_(None), CrmTask.due_date < today)) or 0,
    }


def weekly_body(cfg: Settings, c: Company, name: str, w: dict, today: date) -> tuple[str, str]:
    start = today - timedelta(days=7)
    lines = [
        f"Chào {name},", "",
        f"Báo cáo CRM tuần {_fmt(start)} – {_fmt(today - timedelta(days=1))} của {c.name}:", "",
        f"  • Lead mới: {w['new_leads']}",
        f"  • Chốt thắng: {w['won']}   ·   Thua: {w['lost']}",
        f"  • Việc đã xong: {w['tasks_done']}   ·   Ghi chú mới: {w['notes']}",
        f"  • Việc đang quá hạn: {w['overdue']}",
        "", "Pipeline hiện tại:",
    ]
    lines += [f"  {label}: {w['by_stage'].get(k, 0)}" for k, label in CRM_STAGES.items()]
    lines += ["", f"Mở CRM: {_crm_url(cfg)}", "", "Trân trọng,", "Đội ngũ LeadScan"]
    return f"[LeadScan CRM] Báo cáo tuần: {w['new_leads']} lead mới, {w['won']} chốt thắng", "\n".join(lines) + "\n"


def send_weekly(db: Session, cfg: Settings | None = None, today: date | None = None) -> int:
    cfg = cfg or get_settings()
    today = today or vn_today()
    sent = 0
    for c in gold_companies(db, cfg):
        to = notify.company_contact(db, c.id)  # báo cáo cấp doanh nghiệp → 1 email cho người liên hệ
        if not to or not _members(db, c.id):
            continue
        subject, body = weekly_body(cfg, c, to[1], weekly_for(db, c.id, today), today)
        if notify.send_mail(cfg, subject, body, to=to[0]):
            sent += 1
    return sent

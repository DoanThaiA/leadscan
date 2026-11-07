"""Celery: hàng đợi việc nền (Redis làm broker). Sau này dùng thêm cho crawl & AI.

Chạy worker + lịch định kỳ (beat):
    celery -A app.worker worker -l info            (Windows dev: thêm --pool=solo)
    celery -A app.worker beat -l info
"""

import logging
from datetime import timedelta

from celery import Celery
from sqlalchemy import delete

from app.config import get_settings

log = logging.getLogger("leadscan.worker")

_cfg = get_settings()
celery_app = Celery("leadscan", broker=_cfg.redis_url)
celery_app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,  # worker chết giữa chừng thì việc được giao lại
    worker_prefetch_multiplier=1,
    task_always_eager=_cfg.celery_eager,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,
    timezone="Asia/Ho_Chi_Minh",
    beat_schedule={
        "cleanup-hourly": {"task": "leadscan.cleanup", "schedule": 3600.0},
    },
)


@celery_app.task(name="leadscan.notify_new_registration")
def notify_new_registration_task(company_id: int) -> None:
    from app.db import new_session
    from app.models import Company
    from app.services.notify import notify_new_registration

    with new_session() as db:
        c = db.get(Company, company_id)
        if c:
            notify_new_registration(get_settings(), c)


@celery_app.task(name="leadscan.cleanup")
def cleanup_task() -> None:
    """Xoá phiên đăng nhập hết hạn và lượt đếm rate limit cũ."""
    from app.db import new_session, utcnow
    from app.models import AdminSession, MemberSession, PaymentOrder, RateHit

    with new_session() as db:
        s = db.execute(delete(AdminSession).where(AdminSession.expires_at < utcnow())).rowcount
        s += db.execute(delete(MemberSession).where(MemberSession.expires_at < utcnow())).rowcount
        db.query(PaymentOrder).filter(PaymentOrder.status == "pending", PaymentOrder.expires_at < utcnow()).update(
            {"status": "expired"}, synchronize_session=False
        )
        r = db.execute(delete(RateHit).where(RateHit.created_at < utcnow() - timedelta(days=1))).rowcount
        db.commit()
    log.info("Dọn dẹp: %s phiên hết hạn, %s lượt rate limit cũ", s, r)


@celery_app.task(name="leadscan.send_invoice_request")
def send_invoice_request_task(invoice_id: int) -> None:
    from app.db import new_session, utcnow
    from app.models import InvoiceRequest
    from app.services.notify import send_invoice_request

    with new_session() as db:
        inv = db.get(InvoiceRequest, invoice_id)
        if inv and send_invoice_request(get_settings(), inv):
            inv.email_sent_at = utcnow()
            db.commit()


@celery_app.task(name="leadscan.send_password_reset")
def send_password_reset_task(email: str, name: str, token: str) -> None:
    from app.services.notify import send_password_reset

    send_password_reset(get_settings(), email, name, token)


def enqueue(task, *args) -> None:
    """Đưa việc vào hàng đợi; Redis lỗi thì chỉ ghi log (dữ liệu chính đã nằm trong DB)."""
    try:
        task.apply_async(args, retry=False)
    except Exception as e:  # noqa: BLE001
        log.warning("Không đưa được việc %s vào hàng đợi: %s", task.name, e)


def enqueue_new_registration(company_id: int) -> None:
    """Redis lỗi cũng không sao: hồ sơ đã lưu trong DB, chỉ mất email báo."""
    try:
        notify_new_registration_task.apply_async((company_id,), retry=False)
    except Exception as e:  # noqa: BLE001
        log.warning("Không đưa được việc báo email cho khách hàng %s vào hàng đợi: %s", company_id, e)

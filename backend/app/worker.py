"""Celery: hàng đợi việc nền (Redis làm broker): email, so khớp cơ hội (embedding Cohere + pgvector), dọn dẹp.

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


@celery_app.task(name="leadscan.send_welcome")
def send_welcome_task(company_id: int) -> None:
    """Email chào mừng tới tài khoản thành viên vừa tạo khi đăng ký."""
    from sqlalchemy import select

    from app.db import new_session
    from app.models import Company, MemberUser
    from app.services.notify import send_welcome

    with new_session() as db:
        c = db.get(Company, company_id)
        u = db.scalar(select(MemberUser).where(MemberUser.company_id == company_id).order_by(MemberUser.id))
        if c and u:
            send_welcome(get_settings(), c, u.email, u.full_name)


@celery_app.task(name="leadscan.notify_payment")
def notify_payment_task(order_id: int) -> None:
    """Đơn vừa được ghi nhận đã thanh toán → email cho thành viên + báo quản trị."""
    from sqlalchemy import select

    from app.db import new_session
    from app.models import MemberUser, PaymentOrder
    from app.services.notify import notify_payment_admin, send_payment_success

    cfg = get_settings()
    with new_session() as db:
        o = db.get(PaymentOrder, order_id)
        if not o or o.status != "paid":
            return
        u = db.get(MemberUser, o.created_by_id) if o.created_by_id else None
        if not u or not u.is_active:
            u = db.scalar(
                select(MemberUser).where(MemberUser.company_id == o.company_id, MemberUser.is_active).order_by(MemberUser.id)
            )
        if u:
            send_payment_success(cfg, o, u.email, u.full_name)
        notify_payment_admin(cfg, o)


@celery_app.task(name="leadscan.send_search_request")
def send_search_request_task(req_id: int) -> None:
    """Thành viên gửi yêu cầu Enrich tìm kiếm cơ hội → email báo quản trị."""
    from app.db import new_session, utcnow
    from app.models import SearchRequest
    from app.services.notify import notify_search_request

    with new_session() as db:
        r = db.get(SearchRequest, req_id)
        if r and notify_search_request(get_settings(), r):
            r.email_sent_at = utcnow()
            db.commit()


# ------------------------------------------------------------------ so khớp cơ hội (chạy nền)

MATCH_RETRIES = 3  # ít lần thử lại: mỗi lần gọi Cohere đều tính vào hạn mức 1.000 lần/tháng của khoá Trial


def _retry_delay(retries: int) -> int:
    return min(600, 30 * 2**retries)  # 30s, 60s, 120s


def _run_match(task, fn, label: str):
    """Chạy so khớp có embedding; lỗi tạm thì thử lại, lỗi không thử lại được / hết lượt thử → chạy dự phòng không embedding.

    fn(semantic: bool) -> int, tự commit. Trả về (số cặp phù hợp, ghi chú nếu đã chạy dự phòng).
    """
    from sqlalchemy.exc import IntegrityError, OperationalError

    from app.services.embedding import EmbeddingError

    try:
        return fn(True), ""
    except (IntegrityError, OperationalError) as e:  # 2 việc nền ghi cùng lúc → thử lại
        if task.request.retries < task.max_retries:
            raise task.retry(exc=e, countdown=5) from e
        raise
    except EmbeddingError as e:
        if e.retryable and task.request.retries < task.max_retries:
            raise task.retry(exc=e, countdown=_retry_delay(task.request.retries)) from e
        log.warning("%s: không lấy được embedding (%s) → so khớp bằng tiêu chí + từ khoá", label, e)
        return fn(False), f"So khớp không dùng ngữ nghĩa: {e}"


@celery_app.task(name="leadscan.match_request", bind=True, max_retries=MATCH_RETRIES)
def match_request_task(self, req_id: int) -> None:
    """Phiếu tìm cơ hội vừa gửi / đổi trạng thái → nhúng Cohere, ứng viên pgvector, chấm điểm, thêm vào Tất cả cơ hội."""
    from celery.exceptions import Retry

    from app.db import new_session, utcnow
    from app.models import SearchRequest
    from app.services import matching

    with new_session() as db:
        r = db.get(SearchRequest, req_id)
        if not r:
            return
        r.match_status = "running"
        db.commit()

        def run(semantic: bool) -> int:
            try:
                n = matching.match_request(db, r, semantic=semantic)
                db.commit()
                return n
            except Exception:
                db.rollback()
                raise

        try:
            n, note = _run_match(self, run, f"Phiếu tìm #{req_id}")
        except Retry:
            r.match_status, r.match_error = "pending", "Đang thử lại"
            db.commit()
            raise
        except Exception as e:
            r.match_status, r.match_error = "error", str(e)[:300]
            db.commit()
            log.exception("Phiếu tìm #%s so khớp lỗi", req_id)
            return
        r.match_status, r.match_error, r.matched_at = "done", note[:300], utcnow()
        db.commit()
        log.info("Phiếu tìm #%s: %s cơ hội phù hợp%s", req_id, n, " (dự phòng)" if note else "")


@celery_app.task(name="leadscan.match_opportunity", bind=True, max_retries=MATCH_RETRIES)
def match_opportunity_task(self, opp_id: int) -> None:
    """Phiếu cơ hội vừa thêm / sửa / đổi trạng thái → so với các phiếu tìm cơ hội đã có."""
    from celery.exceptions import Retry

    from app.db import new_session
    from app.models import Opportunity
    from app.services import matching

    with new_session() as db:
        o = db.get(Opportunity, opp_id)
        if not o:
            return

        def run(semantic: bool) -> int:
            try:
                n = matching.match_opportunity(db, o, semantic=semantic)
                db.commit()
                return n
            except Exception:
                db.rollback()
                raise

        try:
            n, note = _run_match(self, run, f"Cơ hội {o.code}")
        except Retry:
            raise
        except Exception:
            log.exception("Cơ hội #%s so khớp lỗi", opp_id)
            return
        log.info("Cơ hội %s: khớp %s phiếu tìm%s", o.code, n, " (dự phòng)" if note else "")


def enqueue(task, *args) -> bool:
    """Đưa việc vào hàng đợi; Redis lỗi thì chỉ ghi log (dữ liệu chính đã nằm trong DB). Trả về False nếu lỗi."""
    try:
        task.apply_async(args, retry=False)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Không đưa được việc %s vào hàng đợi: %s", task.name, e)
        return False


def enqueue_new_registration(company_id: int) -> None:
    """Báo quản trị + chào mừng khách. Redis lỗi cũng không sao: hồ sơ đã lưu trong DB, chỉ mất email."""
    enqueue(notify_new_registration_task, company_id)
    enqueue(send_welcome_task, company_id)

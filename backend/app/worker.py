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
        # quét thông báo cơ hội mới chưa gửi email (vd. nhập cơ hội hàng loạt bằng lệnh CLI)
        "match-digest": {"task": "leadscan.send_match_digest", "schedule": 900.0},
        # hoa hồng đối tác hết thời gian giữ → Khả dụng
        "partner-release": {"task": "leadscan.partner_release_due", "schedule": 3600.0},
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


@celery_app.task(name="leadscan.purge_files", bind=True, max_retries=5)
def purge_files_task(self, keys: list[str]) -> None:
    """Xoá tệp trên Cloudflare R2 (tệp bị bỏ khỏi phiếu, phiếu bị xoá, tệp upload bỏ dở)."""
    from app.services import storage

    keys = [k for k in keys if k]
    if not keys or not storage.configured():
        return
    try:
        storage.backend().delete(keys)
    except Exception as e:  # noqa: BLE001 — R2 lỗi tạm: thử lại sau
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * 2**self.request.retries) from e
        log.exception("Không xoá được %s tệp trên R2", len(keys))


def _cleanup_orphan_attachments(db) -> list[str]:
    """Tệp admin tải lên nhưng không lưu vào phiếu nào sau 24 giờ → xoá trên R2 và trong DB."""
    from sqlalchemy import select

    from app.db import utcnow
    from app.models import OpportunityAttachment
    from app.services.attachments import ORPHAN_HOURS

    old = db.scalars(
        select(OpportunityAttachment).where(
            OpportunityAttachment.opportunity_id.is_(None), OpportunityAttachment.created_at < utcnow() - timedelta(hours=ORPHAN_HOURS)
        )
    ).all()
    keys = [k for a in old for k in (a.key, a.thumb_key) if k]
    for a in old:
        db.delete(a)
    return keys  # xoá trên R2 sau khi DB đã commit


@celery_app.task(name="leadscan.cleanup")
def cleanup_task() -> None:
    """Xoá phiên đăng nhập hết hạn, lượt đếm rate limit cũ, tệp đính kèm upload bỏ dở."""
    from app.db import new_session, utcnow
    from app.models import AdminSession, MemberSession, PartnerOtp, PartnerSession, PaymentOrder, RateHit

    with new_session() as db:
        s = db.execute(delete(AdminSession).where(AdminSession.expires_at < utcnow())).rowcount
        s += db.execute(delete(MemberSession).where(MemberSession.expires_at < utcnow())).rowcount
        s += db.execute(delete(PartnerSession).where(PartnerSession.expires_at < utcnow())).rowcount
        db.execute(delete(PartnerOtp).where(PartnerOtp.created_at < utcnow() - timedelta(days=1)))
        db.query(PaymentOrder).filter(PaymentOrder.status == "pending", PaymentOrder.expires_at < utcnow()).update(
            {"status": "expired"}, synchronize_session=False
        )
        r = db.execute(delete(RateHit).where(RateHit.created_at < utcnow() - timedelta(days=1))).rowcount
        orphan_keys = _cleanup_orphan_attachments(db)
        db.commit()
    if orphan_keys:
        purge_files_task.apply(args=[orphan_keys])
    log.info("Dọn dẹp: %s phiên hết hạn, %s lượt rate limit cũ, %s tệp đính kèm bỏ dở", s, r, len(orphan_keys))


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


EINVOICE_RETRIES = 3


def run_einvoice(invoice_id: int) -> tuple[str, str]:
    """Xuất HĐĐT qua IAM cho 1 yêu cầu hoá đơn. Trả (kết quả, thông báo lỗi):
    'issued' | 'draft' | 'skip' | 'retry' (lỗi mạng/IAM tạm thời) | 'error'. Lỗi đã được ghi vào einvoice_error.
    """
    from app.db import new_session
    from app.models import InvoiceRequest
    from app.services import einvoice

    cfg = get_settings()
    with new_session() as db:
        inv = db.get(InvoiceRequest, invoice_id)
        if not inv or inv.status == "issued":
            return "skip", ""
        try:
            return einvoice.issue(db, cfg, inv), ""
        except einvoice.IamError as e:
            db.rollback()
            inv = db.get(InvoiceRequest, invoice_id)
            einvoice.record_error(db, inv, e)
            log.warning("HĐĐT yêu cầu #%s (đơn %s) lỗi: %s", invoice_id, inv.order.code, e.message)
            return ("retry" if e.retryable else "error"), e.message


@celery_app.task(name="leadscan.issue_einvoice", bind=True, max_retries=EINVOICE_RETRIES)
def issue_einvoice_task(self, invoice_id: int) -> None:
    """Xuất hoá đơn điện tử IAM. Lỗi mạng → thử lại sau 1, 2, 4 phút; vẫn lỗi → email kế toán xuất thủ công."""
    result, _ = run_einvoice(invoice_id)
    if result == "retry" and self.request.retries < self.max_retries and not get_settings().celery_eager:
        raise self.retry(countdown=60 * 2**self.request.retries)
    if result in ("retry", "error"):
        from app.db import new_session
        from app.models import InvoiceRequest

        with new_session() as db:
            inv = db.get(InvoiceRequest, invoice_id)
            emailed = bool(inv and inv.email_sent_at)
        if not emailed:
            send_invoice_request_task.apply(args=[invoice_id])  # dự phòng: kế toán nhận email kèm lý do lỗi


@celery_app.task(name="leadscan.einvoice_for_order")
def einvoice_for_order_task(order_id: int) -> None:
    """Đơn vừa thanh toán → lấy thông tin doanh nghiệp đã đăng ký, tạo yêu cầu hoá đơn và xuất HĐĐT luôn."""
    from sqlalchemy.exc import IntegrityError

    from app.db import new_session
    from app.models import PaymentOrder
    from app.services import einvoice

    with new_session() as db:
        o = db.get(PaymentOrder, order_id)
        if not o or o.status != "paid" or o.invoice:
            return
        try:
            inv = einvoice.auto_request(db, o)
        except IntegrityError:  # khách vừa gửi form cùng lúc → dùng yêu cầu của khách
            db.rollback()
            return
        if not inv:
            log.info("Đơn %s: thiếu tên/MST/địa chỉ doanh nghiệp → chờ khách gửi thông tin xuất hoá đơn", o.code)
            return
        invoice_id = inv.id
    if not enqueue(issue_einvoice_task, invoice_id):
        issue_einvoice_task.apply(args=[invoice_id])


@celery_app.task(name="leadscan.send_password_reset")
def send_password_reset_task(email: str, name: str, token: str) -> None:
    from app.services.notify import send_password_reset

    send_password_reset(get_settings(), email, name, token)


@celery_app.task(name="leadscan.send_partner_password_reset")
def send_partner_password_reset_task(email: str, name: str, token: str) -> None:
    from app.services.notify import send_partner_password_reset

    send_partner_password_reset(get_settings(), email, name, token)


@celery_app.task(name="leadscan.send_partner_welcome")
def send_partner_welcome_task(email: str, name: str, code: str) -> None:
    from app.services.notify import send_partner_welcome

    send_partner_welcome(get_settings(), email, name, code)


@celery_app.task(name="leadscan.send_partner_submission_update")
def send_partner_submission_update_task(sub_id: int) -> None:
    """Email báo đối tác kết quả xác minh cơ hội đã gửi."""
    from app.db import new_session
    from app.models import PartnerSubmission
    from app.services.notify import send_partner_submission_update

    with new_session() as db:
        s = db.get(PartnerSubmission, sub_id)
        if s:
            send_partner_submission_update(get_settings(), s)


@celery_app.task(name="leadscan.send_partner_withdrawal_update")
def send_partner_withdrawal_update_task(wid: int) -> None:
    from app.db import new_session
    from app.models import PartnerWithdrawal
    from app.services.notify import send_partner_withdrawal_update

    with new_session() as db:
        w = db.get(PartnerWithdrawal, wid)
        if w:
            send_partner_withdrawal_update(get_settings(), w)


@celery_app.task(name="leadscan.partner_release_due")
def partner_release_due_task() -> None:
    from app.db import new_session
    from app.services.partner_wallet import release_due

    with new_session() as db:
        n = release_due(db)
    if n:
        log.info("Ví đối tác: %s khoản hoa hồng chuyển sang Khả dụng", n)


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
    """Thành viên gửi yêu cầu Enrich tìm kiếm cơ hội → email báo quản trị (kèm số cơ hội hệ thống đã tự tìm được)."""
    from sqlalchemy import func, select

    from app.db import new_session, utcnow
    from app.models import SearchRequest, SearchRequestMatch
    from app.services.notify import notify_search_request

    with new_session() as db:
        r = db.get(SearchRequest, req_id)
        if not r:
            return
        n = db.scalar(select(func.count()).select_from(SearchRequestMatch).where(SearchRequestMatch.request_id == r.id)) if r.match_status == "done" else None
        if notify_search_request(get_settings(), r, n):
            r.email_sent_at = utcnow()
            db.commit()


MATCH_DIGEST_DELAY = 120  # chờ 2 phút để gộp nhiều cơ hội mới (vd. admin mở bán liên tiếp) vào 1 email


@celery_app.task(name="leadscan.send_match_digest")
def send_match_digest_task() -> None:
    """Email gộp "có cơ hội mới phù hợp" cho từng doanh nghiệp có thông báo chưa gửi email.

    Chỉ báo cơ hội còn khớp phiếu tìm đang tìm kiếm liên tục. Nhận việc bằng UPDATE ... WHERE emailed_at IS NULL
    nên 2 lượt chạy song song không gửi trùng.
    """
    from sqlalchemy import select, update

    from app.db import new_session, utcnow
    from app.models import MemberNotification, MemberUser, Opportunity, SearchRequest, SearchRequestMatch
    from app.services.notify import send_match_digest

    cfg = get_settings()
    with new_session() as db:
        company_ids = db.scalars(select(MemberNotification.company_id).where(MemberNotification.emailed_at.is_(None)).distinct()).all()
        for cid in company_ids:
            now = utcnow()
            ids = db.scalars(select(MemberNotification.id).where(MemberNotification.company_id == cid, MemberNotification.emailed_at.is_(None))).all()
            claimed = db.execute(
                update(MemberNotification).where(MemberNotification.id.in_(ids), MemberNotification.emailed_at.is_(None)).values(emailed_at=now)
            ).rowcount
            db.commit()
            if not claimed:
                continue
            rows = db.execute(
                select(MemberNotification, SearchRequest)
                .join(SearchRequest, SearchRequest.id == MemberNotification.request_id)
                .join(Opportunity, Opportunity.id == MemberNotification.opportunity_id)
                .join(
                    SearchRequestMatch,
                    (SearchRequestMatch.request_id == MemberNotification.request_id)
                    & (SearchRequestMatch.opportunity_id == MemberNotification.opportunity_id),
                )
                .where(
                    MemberNotification.id.in_(ids),
                    MemberNotification.emailed_at == now,
                    MemberNotification.read_at.is_(None),  # khách đã xem trong cổng thì thôi báo qua email
                    SearchRequest.status == "open",
                    Opportunity.status == "published",
                )
                .order_by(SearchRequest.id, MemberNotification.score.desc())
            ).unique().all()
            groups: dict[int, tuple] = {}
            for n, req in rows:
                groups.setdefault(req.id, (req, []))[1].append((n.opportunity, n.score))
            if not groups:
                continue
            users = db.scalars(select(MemberUser).where(MemberUser.company_id == cid, MemberUser.is_active).order_by(MemberUser.id)).all()
            for u in users:
                send_match_digest(cfg, u.email, u.full_name, list(groups.values()))
            log.info("Báo %s cơ hội mới phù hợp cho doanh nghiệp #%s (%s người nhận)", len(rows), cid, len(users))


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


def _finish_request(r, note: str = "") -> None:
    """So khớp xong. Phiếu vẫn ở trạng thái "Tìm kiếm liên tục" — cơ hội mới mở bán sẽ tiếp tục được so với phiếu."""
    from app.db import utcnow

    r.match_status, r.match_error, r.matched_at = "done", note[:300], utcnow()


def match_request_now(req_id: int) -> None:
    """So khớp ngay khi khách gửi phiếu tìm cơ hội → kết quả có liền trong lúc gửi, không chờ việc nền hay quản trị.

    Cohere lỗi: so khớp dự phòng (tiêu chí + từ khoá) để khách vẫn có kết quả ngay; lỗi tạm thời thì xếp việc nền
    chạy lại bằng ngữ nghĩa khi Cohere ổn (không làm phiếu quay về "đang tìm"). Lỗi khác → giao cho việc nền như cũ.
    """
    from app.db import new_session
    from app.models import SearchRequest
    from app.services import matching
    from app.services.embedding import EmbeddingError

    with new_session() as db:
        r = db.get(SearchRequest, req_id)
        if not r:
            return
        r.match_status = "running"
        db.commit()
        refine = False
        try:
            try:
                n = matching.match_request(db, r, semantic=True)
                note = ""
            except EmbeddingError as e:
                db.rollback()
                log.warning("Phiếu tìm #%s: không lấy được embedding (%s) → so khớp bằng tiêu chí + từ khoá", req_id, e)
                refine = e.retryable
                n = matching.match_request(db, r, semantic=False)
                note = f"So khớp không dùng ngữ nghĩa: {e}"
            _finish_request(r, note)
            db.commit()
        except Exception:  # noqa: BLE001 — vd. 2 việc ghi cùng lúc: để việc nền thử lại
            db.rollback()
            log.exception("Phiếu tìm #%s so khớp tại chỗ lỗi → chuyển sang việc nền", req_id)
            r.match_status = "pending"
            db.commit()
            if not enqueue(match_request_task, req_id):
                match_request_task.apply(args=[req_id])
            return
        log.info("Phiếu tìm #%s: %s cơ hội phù hợp%s", req_id, n, " (dự phòng)" if note else "")
    if refine:
        enqueue(match_request_task, req_id, True)


@celery_app.task(name="leadscan.match_request", bind=True, max_retries=MATCH_RETRIES)
def match_request_task(self, req_id: int, refine: bool = False) -> None:
    """Phiếu tìm cơ hội đổi trạng thái / cần so khớp lại → nhúng Cohere, ứng viên pgvector, chấm điểm, thêm vào Tất cả cơ hội.

    refine=True: phiếu đã có kết quả dự phòng, chỉ chấm lại bằng ngữ nghĩa — không đưa phiếu về "đang tìm",
    lỗi thì giữ nguyên kết quả đang có.
    """
    from celery.exceptions import Retry

    from app.db import new_session
    from app.models import SearchRequest
    from app.services import matching

    with new_session() as db:
        r = db.get(SearchRequest, req_id)
        if not r:
            return
        if not refine:
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
            if not refine:
                r.match_status, r.match_error = "pending", "Đang thử lại"
                db.commit()
            raise
        except Exception as e:
            if not refine:
                r.match_status, r.match_error = "error", str(e)[:300]
                db.commit()
            log.exception("Phiếu tìm #%s so khớp lỗi", req_id)
            return
        _finish_request(r, note)
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
    if n:
        try:  # có phiếu tìm khớp → email gộp sau ít phút (khách có thể đã xem thông báo trong cổng)
            send_match_digest_task.apply_async(countdown=MATCH_DIGEST_DELAY, retry=False)
        except Exception as e:  # noqa: BLE001 — Redis lỗi: lượt quét định kỳ sẽ gửi sau
            log.warning("Không xếp được email báo cơ hội mới: %s", e)


def deliver_job_application(app_id: int) -> bool:
    """Gửi hồ sơ ứng viên về hộp thư tuyển dụng; gửi được thì ghi email_sent_at (admin thấy "Đã gửi")."""
    from app.db import new_session, utcnow
    from app.models import JobApplication
    from app.services import cv_files
    from app.services.notify import send_job_application
    from app.services.storage import StorageError

    with new_session() as db:
        a = db.get(JobApplication, app_id)
        if not a:
            return False
        if a.email_sent_at:
            return True
        cv_data = None
        if a.cv_key:  # lấy file CV từ R2 để đính kèm email
            try:
                cv_data = cv_files.fetch(a.cv_key)
            except StorageError:
                log.exception("Không lấy được CV của hồ sơ #%s trên R2", app_id)
                return False
        if not send_job_application(get_settings(), a, cv_data):
            return False
        a.email_sent_at = utcnow()
        db.commit()
        return True


def deliver_application_receipt(app_id: int) -> bool:
    from app.db import new_session
    from app.models import JobApplication
    from app.services.notify import send_application_receipt

    with new_session() as db:
        a = db.get(JobApplication, app_id)
        return bool(a) and send_application_receipt(get_settings(), a)


@celery_app.task(name="leadscan.send_job_application", bind=True, max_retries=3)
def send_job_application_task(self, app_id: int) -> None:
    from app.services.notify import mail_provider

    cfg = get_settings()
    if not deliver_job_application(app_id) and mail_provider(cfg) and not cfg.celery_eager:
        # Resend/SMTP/R2 lỗi tạm → thử lại sau 2, 4, 8 phút
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120 * 2**self.request.retries)


@celery_app.task(name="leadscan.send_application_receipt")
def send_application_receipt_task(app_id: int) -> None:
    deliver_application_receipt(app_id)


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


def enqueue_job_application(app_id: int) -> None:
    """Hồ sơ đã lưu DB → gửi email về hộp thư tuyển dụng + xác nhận cho ứng viên (chạy nền).

    Không có Redis (vd. máy dev) thì gửi luôn trong request để hồ sơ vẫn tới hộp thư.
    """
    if enqueue(send_job_application_task, app_id):
        enqueue(send_application_receipt_task, app_id)
    else:
        deliver_job_application(app_id)
        deliver_application_receipt(app_id)

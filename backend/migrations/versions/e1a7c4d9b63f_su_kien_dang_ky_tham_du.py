"""su kien: trang su kien (events) + dang ky tham du (event_registrations) + seed CEO1989 x Coolmate

Revision ID: e1a7c4d9b63f
Revises: c2f7a4e9d1b6
Create Date: 2026-11-28 10:00:00.000000

"""
from datetime import date, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1a7c4d9b63f'
down_revision: Union[str, Sequence[str], None] = 'c2f7a4e9d1b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_SLUG = "ceo1989-x-coolmate-tu-noi-luc-den-tang-truong"

SEED_INTRO = """Đây không chỉ là một buổi tham quan doanh nghiệp. Hai bên cùng chia sẻ, cùng giới thiệu năng lực và nhu cầu, để tìm ra những cơ hội hợp tác cụ thể, mang lại giá trị cho cả Coolmate và các doanh nghiệp thành viên CLB CEO1989.

## Thông tin chung
- **Thời gian**: Thứ Tư, 02/12/2026 · đón khách từ 14:00, chương trình 14:30 – 20:30
- **Địa điểm**: Văn phòng Coolmate – Tòa nhà BMM, Km2 Đường Phùng Hưng, Hà Đông, Hà Nội (buổi tối chuyển sang nhà hàng)
- **Chủ trì chương trình**: CLB CEO1989 (host, điều phối, MC)
- **Chủ nhà**: Coolmate
- **Thành phần**: thành viên CLB CEO1989 và HanoiBA – CLB Xúc tiến thương mại trên nền tảng số (dự kiến 100 người): chủ tịch, phó chủ tịch, trưởng ban, các thành viên và khách mời của hội viên. Phía Coolmate: CEO, CHRO, CXP Manager.
- **Đầu mối CLB CEO1989**: Mr Phúc – 0909802998
- **Đầu mối Coolmate**: Mrs Lan – 0904394843

## Mục tiêu và kết quả mong đợi
- **Học hỏi lẫn nhau** — Coolmate nhận góc nhìn từ nhiều ngành và kinh nghiệm quản trị của các CEO cùng thế hệ; CLB CEO1989 nhận bài học thực tế về D2C, gọi vốn, Go Global, quản trị và văn hóa. Đầu ra: biên bản tóm tắt nội dung chia sẻ.
- **Kết nối giao thương** — hai bên gửi nhu cầu trước, ban tổ chức ghép cặp sẵn để phần giao thương đi thẳng vào trao đổi. Đầu ra: danh sách cặp kết nối chốt ngay tại chỗ.
"""

SEED_AGENDA = """## Thứ Tư, 02/12/2026
- **14:30 – 15:00** · Đón khách, check-in — lễ tân, gửi xe, tea-break
- **15:00 – 15:10** · Khai mạc: chào mừng, giới thiệu mục tiêu buổi giao lưu (Chủ nhiệm CLB + MC; CEO/CHRO Coolmate chào mừng)
- **15:10 – 15:20** · Phần 1 – Giới thiệu hai bên: Coolmate (2') · CLB (5') · mỗi thành viên giới thiệu nhanh sản phẩm/dịch vụ (~1'/người)
- **15:20 – 15:50** · Phần 2 – Coolmate chia sẻ: D2C · Gọi vốn · Go Global · Quản trị, văn hóa & đội ngũ (~10'/chủ đề). CLB CEO1989 chia sẻ năng lực và các mảng có thể hợp tác với Coolmate và giữa các thành viên
- **15:50 – 16:20** · Phần 3 – Hỏi đáp: 5–7 câu gửi trước và câu hỏi tại chỗ
- **16:20 – 16:30** · Phần 4a – Coolmate nêu mong muốn hợp tác theo 5 nhóm
- **16:30 – 17:00** · Phần 4b – Giao thương matching trong phòng
- **17:00 – 17:20** · Phần 5 – Tham quan văn phòng, chụp ảnh, trao quà cảm ơn
- **17:20 – 18:00** · Di chuyển đến nhà hàng
- **18:00 – 20:30** · Phần 6 – Kết nối: gắn kết, tiếp nối trao đổi riêng

## Vai trò hai bên
- **CLB CEO1989 (Host)** — điều phối chương trình, MC, tổng hợp nhu cầu và profile thành viên, ghép cặp kết nối, ghi biên bản, theo dõi hợp tác sau sự kiện.
- **Coolmate (Chủ nhà)** — chuẩn bị phòng, tiếp đón, tea-break, nội dung chia sẻ của ban lãnh đạo và danh sách nhu cầu hợp tác.
"""

SEED_CONTENT = """## Coolmate chia sẻ (Phần 2)
- **D2C** — xây kênh bán trực tiếp và giữ chân khách hàng mua lại
- **Gọi vốn** — chuẩn bị và làm việc với quỹ qua từng vòng
- **Go Global** — chọn sản phẩm, chọn kênh và xử lý điểm nghẽn khi bán ra nước ngoài
- **Quản trị, văn hóa & đội ngũ** — đặt và truyền đạt mục tiêu, giữ văn hóa khi quy mô tăng nhanh

## CLB CEO1989 chia sẻ (Phần 1 và 4b)
- Giới thiệu CLB: lịch sử, số thành viên, cơ cấu ngành nghề, hoạt động tiêu biểu
- Thành viên giới thiệu nhanh doanh nghiệp, sản phẩm/dịch vụ có thể cung cấp
- Trình bày các doanh nghiệp đáp ứng được nhu cầu của Coolmate và mong muốn hợp tác của CLB
- Kinh nghiệm quản trị, văn hóa từ 1–2 thành viên tiêu biểu (lồng vào hỏi đáp nếu còn thời gian)

## Câu hỏi gợi ý (ban tổ chức chọn 5–7 câu, gửi Coolmate trước 01/12)
1. D2C: Làm thế nào để xây kênh bán trực tiếp và giữ chân khách hàng mua lại?
2. Vận hành: Coolmate đầu tư công nghệ, hệ thống quản trị theo cách nào?
3. Bán lẻ: Điều gì khiến Coolmate phát triển kênh offline? Bài học khi triển khai?
4. Gọi vốn: Ở mỗi vòng, nhà đầu tư soi chỉ số nào kỹ nhất?
5. Gọi vốn: Doanh nghiệp truyền thống nên chuẩn bị gì nếu muốn gọi vốn từ quỹ?
6. Go Global: Coolmate chọn sản phẩm và kênh mở đường ra quốc tế thế nào?
7. Go Global: Điểm nghẽn lớn nhất về logistics, thuế, chứng nhận khi bán ra nước ngoài?
8. Quản trị: Coolmate đặt và truyền đạt mục tiêu xuống đội ngũ thế nào?
9. Văn hóa: Giữ văn hóa ra sao khi đội ngũ tăng nhanh?
10. Kết nối: Trong 12 tháng tới, Coolmate cần thêm nhà cung cấp hay đối tác nào?
"""

SEED_MATCHING = """Hai bên gửi nhu cầu trước ngày 30/11; ban tổ chức tổng hợp và ghép cặp sẵn để phần giao thương đi thẳng vào trao đổi. **Nhu cầu bạn điền trong form đăng ký bên dưới chính là dữ liệu để ghép cặp.**

## 1. Chuỗi cung ứng may mặc — đầu mối Mrs Phụng
Nhà cung cấp sản xuất (xưởng may, gia công) và nguyên liệu (vải, sợi) cần đáp ứng:
- **Pháp lý và năng lực sản xuất** — hồ sơ pháp lý, giấy phép môi trường đầy đủ; máy móc, công suất, nhân sự ổn định, bảo trì tốt; giao hàng đúng hạn và phản hồi khiếu nại nhanh.
- **Hệ thống quản lý chất lượng** — quy trình chuẩn từ chuẩn bị sản xuất, kiểm tra nguyên liệu đầu vào, kiểm soát trên chuyền đến kiểm hàng cuối; có phòng lab kiểm nghiệm (thiết bị được hiệu chuẩn) và quy trình khắc phục khi hàng lỗi.
- **Trách nhiệm xã hội, môi trường và hoá chất** — tuân thủ quy định về lao động, lương, giờ làm, phòng cháy chữa cháy, an toàn lao động; kiểm soát nước thải, khí thải, chất thải; quản lý hoá chất theo danh mục chất cấm/hạn chế (RSL/MRSL), có phiếu an toàn hoá chất (SDS).
- **Truy xuất nguồn gốc và bền vững** — truy xuất được theo từng lô vải, lô sợi; ưu tiên doanh nghiệp có chứng nhận GRS, RCS, GOTS, OCS.

## 2. Bán lẻ (Retail) — đầu mối Mrs Tâm
Tìm mặt bằng bán lẻ:
1. **Flagship**: 3 cửa hàng (Hà Nội, TP.HCM, Đà Nẵng), 500–1.000 m²
2. **Concept store**: 6 cửa hàng, 180–300 m²
3. **Kiosk**: 6 cửa hàng, 60–100 m²

Tại các mall lớn: Aeon Mall, Vincom, Lotte, Vạn Hạnh Mall, Crescent… ở TP.HCM, Đà Nẵng, Hà Nội, Cần Thơ, Hải Phòng.

## 3. Thị trường quốc tế — đầu mối Mrs Duyên
Đối tác kinh doanh, phân phối B2B, logistics, forwarder, xuất nhập khẩu tại thị trường Mỹ và Đông Nam Á.

## 4. Marketing — đầu mối Ms Vân
- **Creative & Communication Agency** — xây dựng ý tưởng sáng tạo, triển khai chiến dịch truyền thông tích hợp (IMC), ưu tiên kinh nghiệm ngành Fashion, Sports, Lifestyle.
- **Media Production** — sản xuất TVC, brand video, campaign photoshoot, social video; sáng tạo và sản xuất với chi phí cạnh tranh.
- **Event & Activation Agency** — tổ chức sự kiện thể thao, community activation, khai trương cửa hàng, brand activation tại trung tâm thương mại.
- **KOL/KOC & Influencer Marketing** — network tốt trong thể thao, thời trang, lifestyle; booking số lượng lớn và đo lường hiệu quả.
- **Market Research & Consumer Insights** — nghiên cứu thị trường, hành vi người tiêu dùng, sức khỏe thương hiệu và xu hướng ngành hàng.
- **Retail & Trade Marketing Production** — thiết kế, sản xuất, thi công POSM, booth, pop-up store, window display, các hạng mục truyền thông tại điểm bán; triển khai toàn quốc.
- **OOH & Advertising Media** — khai thác vị trí quảng cáo ngoài trời, màn hình LED, quảng cáo tại trung tâm thương mại và địa điểm thể thao.
- **International Marketing** — triển khai marketing tại Đông Nam Á, ưu tiên Malaysia và Philippines.

## 5. Khách hàng B2B — đầu mối Mrs Phương
Các khách hàng cần đặt hàng đồng phục, quà tặng.

## CLB CEO1989 mong muốn từ Coolmate
- Mua đồng phục, quà tặng
- Học kinh nghiệm D2C, bán lẻ, Go Global
- Dùng kênh của Coolmate để phân phối
- Cơ hội hợp tác chéo giữa các thành viên với nhau
"""

SEED_NOTES = """## Mốc chuẩn bị
- **26/11** — Phát hành thư mời kèm form nhu cầu và câu hỏi, thu phí sự kiện (BTC CLB)
- **28/11** — Coolmate gửi nhu cầu chi tiết 5 nhóm: mua hàng, retail, logistics, B2B, quốc tế
- **30/11** — Thành viên gửi profile, nhu cầu, câu hỏi
- **01/12** — Gửi Coolmate bộ câu hỏi; chốt danh sách tham dự, nhà hàng, chi phí; hoàn thiện slide; Coolmate chuẩn bị phòng, tiếp đón, tea-break
- **02/12** — Chương trình diễn ra
- **Sau sự kiện** — Gửi cảm ơn, ảnh, biên bản tóm tắt, danh sách kết nối; theo dõi các hoạt động hợp tác trong 30 ngày

## Khi đăng ký, vui lòng
- Mô tả rõ **nhu cầu xúc tiến với Coolmate**: bạn có thể cung cấp gì và muốn mua / hợp tác gì.
- Đính kèm **profile doanh nghiệp dạng PDF** để ban tổ chức tổng hợp và ghép cặp trước ngày 30/11.
- Chuyển khoản phí tham dự theo mã QR hiện ra sau khi đăng ký, rồi tải ảnh chụp màn hình giao dịch lên để hệ thống đối soát.

## Liên hệ
- Đầu mối CLB CEO1989: **Mr Phúc – 0909802998**
- Đầu mối Coolmate: **Mrs Lan – 0904394843**
"""


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("host", sa.String(length=200), nullable=False),
        sa.Column("partner", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("venue", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("cover_image", sa.String(length=500), nullable=False),
        sa.Column("banner_image", sa.String(length=500), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False),
        sa.Column("agenda", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("matching", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("fee_member", sa.Integer(), nullable=False),
        sa.Column("fee_guest", sa.Integer(), nullable=False),
        sa.Column("fee_note", sa.String(length=300), nullable=False),
        sa.Column("bank_bin", sa.String(length=10), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("account_no", sa.String(length=40), nullable=False),
        sa.Column("account_name", sa.String(length=120), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("contact_phone", sa.String(length=20), nullable=False),
        sa.Column("notify_email", sa.String(length=200), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_events_status"), ["status"], unique=False)

    op.create_table(
        "event_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("event_title", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("attendee_type", sa.String(length=10), nullable=False),
        sa.Column("needs", sa.Text(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("profile_key", sa.String(length=400), nullable=False),
        sa.Column("profile_filename", sa.String(length=200), nullable=False),
        sa.Column("profile_mime", sa.String(length=100), nullable=False),
        sa.Column("profile_size", sa.BigInteger(), nullable=False),
        sa.Column("proof_key", sa.String(length=400), nullable=False),
        sa.Column("proof_filename", sa.String(length=200), nullable=False),
        sa.Column("proof_mime", sa.String(length=100), nullable=False),
        sa.Column("proof_size", sa.BigInteger(), nullable=False),
        sa.Column("proof_at", sa.DateTime(), nullable=True),
        sa.Column("ocr_status", sa.String(length=12), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("ocr_amount", sa.BigInteger(), nullable=True),
        sa.Column("ocr_checks", sa.JSON(), nullable=True),
        sa.Column("ocr_message", sa.String(length=300), nullable=False),
        sa.Column("ocr_at", sa.DateTime(), nullable=True),
        sa.Column("ocr_tries", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        sa.Column("checked_in", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=False),
        sa.Column("email_sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    with op.batch_alter_table("event_registrations", schema=None) as batch_op:
        for col in ("event_id", "status", "created_at"):
            batch_op.create_index(batch_op.f(f"ix_event_registrations_{col}"), [col], unique=False)

    _seed()


def _seed() -> None:
    """Tạo sẵn sự kiện CLB CEO1989 × Coolmate, đã đăng.

    Tài khoản nhận phí để trống → hệ thống dùng tài khoản thu chung trong .env; chưa có thì trang sự kiện
    vẫn nhận đăng ký nhưng không vẽ được mã QR. Vào Quản trị → Sự kiện để điền BIN / số tài khoản.
    """
    now = datetime.utcnow()
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO events (
                slug, status, title, subtitle, summary, host, partner,
                starts_at, ends_at, venue, address, deadline, capacity,
                cover_image, banner_image, intro, agenda, content, matching, notes,
                fee_member, fee_guest, fee_note,
                bank_bin, bank_name, account_no, account_name,
                contact_name, contact_phone, notify_email,
                published_at, created_by_id, created_at, updated_at
            ) VALUES (
                :slug, :status, :title, :subtitle, :summary, :host, :partner,
                :starts_at, :ends_at, :venue, :address, :deadline, :capacity,
                :cover_image, :banner_image, :intro, :agenda, :content, :matching, :notes,
                :fee_member, :fee_guest, :fee_note,
                '', '', '', '',
                :contact_name, :contact_phone, '',
                :now, NULL, :now, :now
            )
            """
        ),
        {
            "slug": SEED_SLUG,
            "status": "published",
            "title": "Business Matching CLB CEO1989 × Coolmate: Từ nội lực đến tăng trưởng",
            "subtitle": "Chia sẻ kinh nghiệm thực chiến trong vận hành, quản trị và mở rộng doanh nghiệp",
            "summary": (
                "Buổi giao lưu – chia sẻ – kết nối hợp tác giữa CLB CEO1989 và Coolmate tại văn phòng Coolmate "
                "(Hà Đông, Hà Nội): nghe Coolmate chia sẻ về D2C, gọi vốn, Go Global, quản trị và văn hóa, "
                "sau đó giao thương matching theo nhu cầu hai bên đã gửi trước."
            ),
            "host": "CLB CEO1989",
            "partner": "Coolmate",
            "starts_at": datetime(2026, 12, 2, 14, 0),
            "ends_at": datetime(2026, 12, 2, 20, 30),
            "venue": "Văn phòng Coolmate",
            "address": "Tòa nhà BMM, Km2 Đường Phùng Hưng, Hà Đông, Hà Nội",
            "deadline": date(2026, 12, 1),
            "capacity": 100,
            "cover_image": "/su-kien/ceo1989-coolmate-poster.webp",
            "banner_image": "/su-kien/ceo1989-coolmate-go-global.webp",
            "intro": SEED_INTRO,
            "agenda": SEED_AGENDA,
            "content": SEED_CONTENT,
            "matching": SEED_MATCHING,
            "notes": SEED_NOTES,
            "fee_member": 500000,
            "fee_guest": 600000,
            "fee_note": "Thành viên CLB 500.000đ/người · Khách mời ngoài CLB 600.000đ/người. Đóng phí trước ngày 01/12 để ban tổ chức chốt danh sách.",
            "contact_name": "Mr Phúc (CLB CEO1989)",
            "contact_phone": "0909802998",
            "now": now,
        },
    )


def downgrade() -> None:
    with op.batch_alter_table("event_registrations", schema=None) as batch_op:
        for col in ("event_id", "status", "created_at"):
            batch_op.drop_index(batch_op.f(f"ix_event_registrations_{col}"))
    op.drop_table("event_registrations")
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_events_status"))
    op.drop_table("events")

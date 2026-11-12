"""Thành viên tự sửa thông tin tài khoản & doanh nghiệp (/api/member/profile)."""

from sqlalchemy import select

from app.db import new_session
from app.models import Activity, Company
from tests.test_member import member  # noqa: F401  (fixture)


def _form(m, **over):
    p = m.get("/api/member/profile").json()
    body = {k: p[k] for k in ("full_name", "company_name", "industries", "company_size", "province", "address", "website",
                              "contact_name", "contact_position", "contact_phone")}
    body.update(over)
    return body


def test_get_profile(member):  # noqa: F811
    p = member.get("/api/member/profile").json()
    assert p["company_name"] == "Công ty TNHH Bao Bì Minh An" and p["tax_code"] == "0101234567" and p["email"] == "a@minhan.vn"
    assert p["industries"] == ["Bao bì & in ấn", "Nhựa & cao su"] and p["company_size"] == "50–199 nhân sự"
    assert p["contact_name"] == "Nguyễn Văn A" and p["contact_phone"] == "0901234567"
    assert "Bao bì & in ấn" in p["options"]["industries"] and p["options"]["max_industries"] == 8


def test_update_profile_and_history(member):  # noqa: F811
    body = _form(member, full_name="  Trần   Văn B ", company_name="Công ty CP Bao Bì Minh An Phát", industries=["Logistics & vận tải", "Ngành tự nhập"],
                 company_size="200–499 nhân sự", province="Hà Nội", address="Số 1 Láng Hạ", website="minhanphat.vn",
                 contact_name="Lê Thị C", contact_position="Trưởng phòng mua hàng", contact_phone="+84 912 000 111",
                 tax_code="9999999999", email="hack@x.vn")  # 2 trường cuối bị bỏ qua
    r = member.put("/api/member/profile", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["me"]["full_name"] == "Trần Văn B" and j["me"]["company"]["name"] == "Công ty CP Bao Bì Minh An Phát"
    p = j["profile"]
    assert p["website"] == "https://minhanphat.vn" and p["contact_phone"] == "+84912000111" and p["industries"] == ["Logistics & vận tải", "Ngành tự nhập"]
    assert p["tax_code"] == "0101234567" and p["email"] == "a@minhan.vn" and j["changed"] >= 9
    assert member.get("/api/member/auth/me").json()["company"]["address"] == "Số 1 Láng Hạ, Hà Nội"
    with new_session() as db:
        c = db.scalar(select(Company))
        act = db.scalars(select(Activity).where(Activity.company_id == c.id, Activity.kind == "update")).all()[-1].content
    assert "tự cập nhật thông tin" in act and "Tên doanh nghiệp: Công ty TNHH Bao Bì Minh An → Công ty CP Bao Bì Minh An Phát" in act
    # lưu lại y nguyên → không ghi thêm lịch sử
    assert member.put("/api/member/profile", json=_form(member)).json()["changed"] == 0


def test_update_profile_validation(member):  # noqa: F811
    r = member.put("/api/member/profile", json=_form(member, company_name=" ", industries=[], company_size="nhiều", contact_phone="123",
                                                     website="khong hop le", full_name=""))
    assert r.status_code == 422
    f = r.json()["fields"]
    assert set(f) >= {"company_name", "industries", "company_size", "contact_phone", "website", "full_name"}
    r = member.put("/api/member/profile", json=_form(member, industries=[f"Ngành {i}" for i in range(9)]))
    assert r.status_code == 422 and "tối đa 8" in r.json()["fields"]["industries"]
    assert member.get("/api/member/profile").json()["company_name"] == "Công ty TNHH Bao Bì Minh An"  # không lưu gì


def test_profile_requires_login(client):
    assert client.get("/api/member/profile").status_code == 401
    assert client.put("/api/member/profile", json={}).status_code in (401, 403)

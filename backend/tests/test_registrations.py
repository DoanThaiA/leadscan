from sqlalchemy import func, select

from app.db import new_session
from app.models import Company, RateHit
from tests.conftest import valid_form


def _companies():
    with new_session() as db:
        return db.scalars(select(Company)).unique().all()


def test_dang_ky_hop_le_luu_doanh_nghiep_lien_he_chan_dung(client):
    r = client.post("/api/registrations", json=valid_form())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["code"].startswith("LS-")

    with new_session() as db:
        c = db.scalar(select(Company))
        assert c.code == body["code"] and c.status == "new" and c.name == "Công ty TNHH Bao Bì Minh An"
        assert c.website == "https://minhan.vn" and c.tax_key == "0101234567"
        (contact,) = c.contacts
        assert contact.is_primary and contact.email == "a@minhan.vn" and contact.phone == "0901234567"
        assert c.profile.target_regions == ["Miền Bắc"] and c.profile.opp_types == ["Dự án & gói thầu"]
        assert [a.kind for a in c.activities] == ["created"]


def test_loi_kiem_tra_tra_ve_theo_truong(client):
    r = client.post("/api/registrations", json=valid_form(tax_code="123", email="sai", phone="12", agree=False, company_size="?"))
    assert r.status_code == 422
    assert set(r.json()["fields"]) == {"tax_code", "email", "phone", "agree", "company_size"}
    assert _companies() == []


def test_json_khong_hop_le(client):
    r = client.post("/api/registrations", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_honeypot_gia_vo_thanh_cong_khong_luu(client):
    r = client.post("/api/registrations", json=valid_form(website_url="http://spam"))
    assert r.status_code == 200 and r.json()["code"].endswith("-000000")
    assert _companies() == []


def test_thieu_hoac_qua_nhanh_elapsed_ms_bi_chan(client):
    form = valid_form()
    del form["elapsed_ms"]
    assert client.post("/api/registrations", json=form).status_code == 429
    assert client.post("/api/registrations", json=valid_form(elapsed_ms=500)).status_code == 429


def test_trung_ma_so_thue(client):
    assert client.post("/api/registrations", json=valid_form(tax_code="0101234567001")).status_code == 200
    r = client.post("/api/registrations", json=valid_form(tax_code="0101234567-001", email="b@x.vn"))
    assert r.status_code == 409 and "tax_code" in r.json()["fields"]


def test_gioi_han_tan_suat_theo_ip(client):
    for i in range(5):
        assert client.post("/api/registrations", json=valid_form(tax_code=f"010123456{i}")).status_code == 200
    assert client.post("/api/registrations", json=valid_form(tax_code="0101234569")).status_code == 429


def test_rate_limit_chi_tinh_luot_thanh_cong(client):
    client.post("/api/registrations", json=valid_form(tax_code="1"))
    with new_session() as db:
        assert db.scalar(select(func.count()).select_from(RateHit)) == 0


def test_chan_gui_cheo_trang(client):
    r = client.post("/api/registrations", json=valid_form(), headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    ok = client.post("/api/registrations", json=valid_form(), headers={"origin": "https://leadscan.mcv.network"})
    assert ok.status_code == 200


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}

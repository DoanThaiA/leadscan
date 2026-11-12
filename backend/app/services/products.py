"""Danh mục sản phẩm con + từ đồng nghĩa, và địa danh — để so khớp ĐÚNG SẢN PHẨM, không chỉ đúng ngành.

Vì sao cần: ngành "Bao bì & in ấn" gồm cả túi giữ nhiệt, túi PP dệt, túi RPET, túi trồng cây, thùng carton…
Khách chỉ làm túi giữ nhiệt thì cơ hội "túi PP dệt" cùng ngành nhưng SAI sản phẩm, không được điểm cao.

  product_relation(yêu cầu, cơ hội):
    direct      cơ hội nhắc đúng sản phẩm khách tìm (kể cả từ đồng nghĩa: túi giữ lạnh = túi giữ nhiệt)
    equivalent  sản phẩm tương đương / thay thế được (thùng giữ nhiệt ~ túi giữ nhiệt)
    unrelated   cơ hội nêu sản phẩm cụ thể nhưng là sản phẩm khác (túi PP dệt, túi trồng cây…)
    unknown     cơ hội chỉ ghi chung nhóm sản phẩm (túi, bao bì…) → chưa xác nhận được
                (không nhắc gì tới nhóm sản phẩm khách cần → unrelated)
    None        mô tả của khách không nêu sản phẩm nào trong danh mục → không áp dụng

Thêm sản phẩm: thêm 1 dòng vào PRODUCTS (từ đồng nghĩa viết có dấu hoặc không đều được, so sau khi bỏ dấu).
"""

from dataclasses import dataclass

from app.services.embedding import fold


@dataclass(frozen=True)
class Product:
    key: str
    name: str
    industry: str
    terms: tuple[str, ...]
    related: tuple[str, ...] = ()
    family: tuple[str, ...] = ()  # từ chung của nhóm (túi, thùng…) — cơ hội chỉ ghi chung chung vẫn có thể liên quan


_BAG = ("túi", "bag", "bags", "bao bì", "packaging", "đóng gói")
_BOX = ("thùng", "hộp", "box", "bao bì", "packaging", "đóng gói")
_PACK = ("bao bì", "packaging", "đóng gói")


_P = [
    # ---- Bao bì & in ấn: túi các loại
    Product("tui_giu_nhiet", "Túi giữ nhiệt", "Bao bì & in ấn",
            ("túi giữ nhiệt", "túi giữ lạnh", "túi cách nhiệt", "túi bảo ôn", "túi ủ nhiệt", "túi giao hàng giữ nhiệt",
             "túi đựng đồ ăn giữ nhiệt", "túi shipper", "thermal bag", "cooler bag", "insulated bag", "insulated delivery bag",
             "thermal delivery bag", "food delivery bag"),
            ("thung_giu_nhiet", "balo_giao_hang")),
    Product("thung_giu_nhiet", "Thùng / hộp giữ nhiệt", "Bao bì & in ấn",
            ("thùng giữ nhiệt", "hộp giữ nhiệt", "thùng giữ lạnh", "hộp giữ lạnh", "thùng xốp", "hộp xốp", "thùng đá",
             "cooler box", "insulated box", "ice box"),
            ("tui_giu_nhiet",)),
    Product("balo_giao_hang", "Ba lô / túi giao hàng", "Bao bì & in ấn",
            ("ba lô giao hàng", "balo giao hàng", "thùng giao hàng", "delivery backpack", "delivery box"),
            ("tui_giu_nhiet",)),
    Product("tui_pp_det", "Túi / bao PP dệt", "Bao bì & in ấn",
            ("túi pp dệt", "bao pp dệt", "bao pp", "túi pp", "bao dứa", "pp woven bag", "woven bag", "bao bố"),
            ("bao_jumbo",)),
    Product("bao_jumbo", "Bao jumbo / FIBC", "Bao bì & in ấn", ("bao jumbo", "fibc", "bulk bag", "big bag", "bao tấn"), ("tui_pp_det",)),
    Product("tui_rpet", "Túi RPET", "Bao bì & in ấn", ("túi rpet", "rpet", "rpet bag", "túi nhựa tái chế"), ("tui_vai_khong_det", "tui_vai")),
    Product("tui_vai_khong_det", "Túi vải không dệt", "Bao bì & in ấn",
            ("túi vải không dệt", "túi không dệt", "non woven bag", "nonwoven bag", "non woven"), ("tui_rpet", "tui_vai")),
    Product("tui_vai", "Túi vải / tote", "Bao bì & in ấn",
            ("túi vải", "túi canvas", "túi tote", "tote bag", "túi cotton", "túi bố", "canvas bag"), ("tui_vai_khong_det", "tui_rpet")),
    Product("tui_trong_cay", "Túi trồng cây / bầu ươm", "Bao bì & in ấn",
            ("túi trồng cây", "túi bầu", "bầu ươm", "túi ươm cây", "grow bag", "planter bag")),
    Product("tui_nilon", "Túi nilon / PE", "Bao bì & in ấn",
            ("túi nilon", "túi ni lông", "túi nylon", "túi pe", "túi hdpe", "túi ldpe", "túi zip", "túi xốp", "túi rác",
             "poly bag", "plastic bag", "túi nhựa"), ("tui_giay",)),
    Product("tui_giay", "Túi giấy", "Bao bì & in ấn", ("túi giấy", "túi kraft", "paper bag", "kraft bag"), ("tui_nilon", "tui_vai")),
    # ---- Bao bì & in ấn: hộp, thùng, màng, nhãn
    Product("thung_carton", "Thùng / hộp carton", "Bao bì & in ấn",
            ("thùng carton", "hộp carton", "thùng giấy", "carton box", "corrugated box", "thùng sóng", "carton"), ("hop_giay",)),
    Product("hop_giay", "Hộp giấy / hộp cứng", "Bao bì & in ấn",
            ("hộp giấy", "hộp cứng", "hộp quà", "gift box", "paper box", "rigid box"), ("thung_carton",)),
    Product("mang_co", "Màng co / màng quấn", "Bao bì & in ấn",
            ("màng co", "màng quấn", "màng pe", "stretch film", "shrink film", "màng bọc")),
    Product("tem_nhan", "Tem nhãn / decal", "Bao bì & in ấn", ("tem nhãn", "nhãn mác", "decal", "sticker", "label")),
    Product("pallet", "Pallet", "Bao bì & in ấn", ("pallet", "pallet gỗ", "pallet nhựa", "pa lét")),
]
_FAMILY = {"thung_giu_nhiet": _BOX, "thung_carton": _BOX, "hop_giay": _BOX, "mang_co": _PACK, "tem_nhan": _PACK, "pallet": _PACK}
_P = [Product(p.key, p.name, p.industry, p.terms, p.related, _FAMILY.get(p.key, _BAG)) for p in _P]
PRODUCTS: dict[str, Product] = {p.key: p for p in _P}

# cụm đã bỏ dấu → mã sản phẩm, xếp cụm dài trước (để "túi pp dệt" thắng "túi pp")
_TERMS: list[tuple[str, str]] = sorted(
    ((fold(t), p.key) for p in _P for t in (p.name, *p.terms)), key=lambda x: -len(x[0])
)


def find_products(text: str) -> list[str]:
    """Các sản phẩm (mã) xuất hiện trong văn bản, theo thứ tự gặp. Cụm dài khớp trước và "ăn" phần chữ đó."""
    f = f" {fold(text)} "
    found: dict[str, int] = {}
    for term, key in _TERMS:
        needle = f" {term} "
        i = f.find(needle)
        while i >= 0:
            found.setdefault(key, i)
            f = f[: i + 1] + "#" * len(term) + f[i + 1 + len(term):]  # che lại để cụm ngắn hơn không khớp lần nữa
            i = f.find(needle)
    return sorted(found, key=found.get)


def product_names(keys: list[str]) -> list[str]:
    return [PRODUCTS[k].name for k in keys if k in PRODUCTS]


def product_relation(wanted: list[str], text: str) -> tuple[str | None, list[str]]:
    """(quan hệ, các sản phẩm của cơ hội liên quan) — xem docstring module."""
    if not wanted:
        return None, []
    have = find_products(text)
    direct = [k for k in have if k in wanted]
    if direct:
        return "direct", direct
    near = {r for k in wanted for r in PRODUCTS[k].related}
    equiv = [k for k in have if k in near]
    if equiv:
        return "equivalent", equiv
    if have:
        return "unrelated", have
    f = f" {fold(text)} "
    if any(f" {fold(t)} " in f for k in wanted for t in PRODUCTS[k].family):
        return "unknown", []  # chỉ ghi chung (vd. "cần túi đựng hàng", "bao bì") — chưa xác nhận được
    return "unrelated", []  # không nhắc gì tới nhóm sản phẩm khách cần


# ------------------------------------------------------------------ địa danh trong mô tả

# tên chuẩn (như cột tỉnh/thành của phiếu cơ hội) → (miền, các cách viết khác)
PROVINCES: dict[str, tuple[str, tuple[str, ...]]] = {
    "TP. Hồ Chí Minh": ("Miền Nam", ("hồ chí minh", "tp hcm", "tphcm", "hcm", "hcmc", "sài gòn", "saigon", "ho chi minh city")),
    "Hà Nội": ("Miền Bắc", ("hà nội", "hanoi", "ha noi")),
    "Hải Phòng": ("Miền Bắc", ("hải phòng",)),
    "Đà Nẵng": ("Miền Trung", ("đà nẵng", "da nang")),
    "Cần Thơ": ("Miền Nam", ("cần thơ",)),
    "Bình Dương": ("Miền Nam", ("bình dương",)),
    "Đồng Nai": ("Miền Nam", ("đồng nai", "biên hoà", "biên hòa")),
    "Long An": ("Miền Nam", ("long an",)),
    "Bà Rịa - Vũng Tàu": ("Miền Nam", ("bà rịa vũng tàu", "vũng tàu", "bà rịa")),
    "Tây Ninh": ("Miền Nam", ("tây ninh",)),
    "Bình Phước": ("Miền Nam", ("bình phước",)),
    "Tiền Giang": ("Miền Nam", ("tiền giang",)),
    "Bắc Ninh": ("Miền Bắc", ("bắc ninh",)),
    "Bắc Giang": ("Miền Bắc", ("bắc giang",)),
    "Hải Dương": ("Miền Bắc", ("hải dương",)),
    "Hưng Yên": ("Miền Bắc", ("hưng yên",)),
    "Vĩnh Phúc": ("Miền Bắc", ("vĩnh phúc",)),
    "Thái Nguyên": ("Miền Bắc", ("thái nguyên",)),
    "Quảng Ninh": ("Miền Bắc", ("quảng ninh",)),
    "Nghệ An": ("Miền Trung", ("nghệ an",)),
    "Thanh Hoá": ("Miền Trung", ("thanh hoá", "thanh hóa")),
    "Khánh Hoà": ("Miền Trung", ("khánh hoà", "khánh hòa", "nha trang")),
    "Bình Định": ("Miền Trung", ("bình định", "quy nhơn")),
    "Quảng Nam": ("Miền Trung", ("quảng nam",)),
}
_REGION_TERMS = {
    "Miền Nam": ("miền nam", "phía nam", "nam bộ", "đông nam bộ", "tây nam bộ", "southern vietnam", "south vietnam"),
    "Miền Bắc": ("miền bắc", "phía bắc", "bắc bộ", "northern vietnam", "north vietnam"),
    "Miền Trung": ("miền trung", "trung bộ", "central vietnam"),
}
_PLACE_TERMS: list[tuple[str, str]] = sorted(
    [(fold(n), n) for n in PROVINCES]
    + [(fold(a), n) for n, (_, al) in PROVINCES.items() for a in al]
    + [(fold(t), r) for r, ts in _REGION_TERMS.items() for t in ts],
    key=lambda x: -len(x[0]),
)


def find_places(text: str) -> list[str]:
    """Tỉnh/thành và miền khách ghi trong mô tả (tên chuẩn), theo thứ tự gặp."""
    f = f" {fold(text)} "
    found: dict[str, int] = {}
    for term, name in _PLACE_TERMS:
        needle = f" {term} "
        i = f.find(needle)
        while i >= 0:
            found.setdefault(name, i)
            f = f[: i + 1] + "#" * len(term) + f[i + 1 + len(term):]
            i = f.find(needle)
    return sorted(found, key=found.get)


def canonical_province(name: str) -> str:
    """"TP.HCM", "Hồ Chí Minh", "Sài Gòn" → "TP. Hồ Chí Minh"; không nhận ra thì trả nguyên."""
    places = [p for p in find_places(name) if p in PROVINCES]
    return places[0] if places else name


def province_region(name: str) -> str:
    p = PROVINCES.get(canonical_province(name))
    return p[0] if p else ""

"""Sinh chuỗi VietQR (chuẩn EMVCo QR của NAPAS) để khách quét chuyển khoản đúng số tiền + nội dung."""


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def build_payload(bank_bin: str, account_no: str, amount: int, content: str) -> str:
    """Chuỗi QR chuyển khoản nhanh 24/7 tới tài khoản (dịch vụ QRIBFTTA), có sẵn số tiền và nội dung."""
    beneficiary = _tlv("00", bank_bin) + _tlv("01", account_no)
    merchant = _tlv("00", "A000000727") + _tlv("01", beneficiary) + _tlv("02", "QRIBFTTA")
    body = (
        _tlv("00", "01")
        + _tlv("01", "12")  # QR động (dùng 1 lần, có số tiền)
        + _tlv("38", merchant)
        + _tlv("53", "704")  # VND
        + _tlv("54", str(int(amount)))
        + _tlv("58", "VN")
        + _tlv("62", _tlv("08", content[:25]))
        + "6304"
    )
    return body + crc16_ccitt(body)

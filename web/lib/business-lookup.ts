/**
 * Tra cứu thông tin doanh nghiệp theo mã số thuế qua API công khai của VietQR
 * (https://api.vietqr.io/v2/business/{taxCode}, dữ liệu tổng hợp từ Tổng cục Thuế).
 *
 * Gọi thẳng từ trình duyệt (API cho phép CORS *) để giới hạn tần suất tính theo IP của từng
 * khách chứ không dồn vào IP máy chủ — API chỉ cho khoảng 2 lượt gọi liên tiếp.
 */

export type BusinessInfo = {
  taxCode: string;
  name: string;
  internationalName: string | null;
  shortName: string | null;
  address: string;
  /** Tỉnh/thành tách từ cuối địa chỉ, đã chuẩn hoá (vd "TP Hà Nội" → "Hà Nội") */
  province: string;
  /** Trạng thái người nộp thuế, vd "NNT đang hoạt động" */
  status: string;
  active: boolean;
};

export type LookupResult =
  | { ok: true; data: BusinessInfo }
  | { ok: false; reason: "invalid" | "not_found" | "rate_limited" | "network"; message: string };

/** Chỉ giữ chữ số và dấu gạch; hợp lệ khi 10 số hoặc 10 số + 3 số chi nhánh */
export function normalizeTaxCode(raw: string): string | null {
  const s = raw.replace(/[^\d-]/g, "");
  const m = /^(\d{10})-?(\d{3})?$/.exec(s);
  if (!m) return null;
  return m[2] ? `${m[1]}-${m[2]}` : m[1];
}

/** "Phường Cầu Giấy, TP Hà Nội" → "Hà Nội"; "…, Tỉnh Bắc Ninh, Việt Nam" → "Bắc Ninh" */
export function provinceFromAddress(address: string): string {
  const parts = address.split(",").map((p) => p.trim()).filter(Boolean);
  while (parts.length && /^vi[eệ]t\s*nam$/i.test(parts[parts.length - 1])) parts.pop();
  const last = parts[parts.length - 1] ?? "";
  const name = last.replace(/^(thành\s+phố|tp\.?|tỉnh)\s*/i, "").trim();
  if (/^(hồ chí minh|hcm)$/i.test(name)) return "TP. Hồ Chí Minh";
  return name;
}

const cache = new Map<string, LookupResult>();

export async function lookupBusiness(rawTaxCode: string, signal?: AbortSignal): Promise<LookupResult> {
  const taxCode = normalizeTaxCode(rawTaxCode);
  if (!taxCode) return { ok: false, reason: "invalid", message: "Mã số thuế gồm 10 hoặc 13 chữ số." };
  const hit = cache.get(taxCode);
  if (hit) return hit;

  const url = `https://api.vietqr.io/v2/business/${encodeURIComponent(taxCode)}`;
  let res: Response;
  try {
    res = await fetch(url, { signal });
    if (res.status === 429) {
      // API báo bận kèm Retry-After (thường 1 giây) — chờ rồi thử lại đúng 1 lần
      const wait = Math.min(Number(res.headers.get("Retry-After")) || 1, 3) * 1000 + 300;
      await new Promise<void>((ok, fail) => {
        const t = setTimeout(ok, wait);
        signal?.addEventListener("abort", () => { clearTimeout(t); fail(new DOMException("Aborted", "AbortError")); }, { once: true });
      });
      res = await fetch(url, { signal });
    }
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    return { ok: false, reason: "network", message: "Không kết nối được dịch vụ tra cứu. Bạn vui lòng tự nhập thông tin." };
  }
  if (res.status === 429) {
    return { ok: false, reason: "rate_limited", message: "Dịch vụ tra cứu đang bận, vui lòng thử lại sau vài giây." };
  }

  let j: { code?: string; desc?: string; data?: Record<string, string | null> | null } = {};
  try {
    j = await res.json();
  } catch {}
  const d = j.data;
  let out: LookupResult;
  if (res.ok && j.code === "00" && d?.name) {
    const address = (d.address ?? "").trim();
    const status = (d.status ?? "").trim();
    out = {
      ok: true,
      data: {
        taxCode: d.id ?? taxCode,
        name: d.name.trim(),
        internationalName: d.internationalName ?? null,
        shortName: d.shortName ?? null,
        address,
        province: provinceFromAddress(address),
        status,
        active: !status || /đang hoạt động/i.test(status),
      },
    };
  } else if (j.code) {
    out = { ok: false, reason: "not_found", message: "Không tìm thấy doanh nghiệp với mã số thuế này. Vui lòng kiểm tra lại hoặc tự nhập thông tin." };
  } else {
    return { ok: false, reason: "network", message: "Dịch vụ tra cứu tạm thời không phản hồi. Bạn vui lòng tự nhập thông tin." };
  }
  cache.set(taxCode, out); // chỉ cache kết quả chắc chắn (tìm thấy / không tồn tại)
  return out;
}

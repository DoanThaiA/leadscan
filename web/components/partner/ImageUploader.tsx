"use client";

import { useEffect, useRef, useState } from "react";

import { errMsg, papi } from "@/lib/partner/api";
import type { PartnerImage } from "@/lib/partner/submissions";

interface Cfg { enabled: boolean; max_files: number; max_mb: number; types: string[] }

/**
 * Ảnh gắn vào cơ hội gửi: tải thẳng lên kho lưu trữ (link ký sẵn) rồi báo máy chủ kiểm tra (đúng ảnh, xoá EXIF/GPS, tạo ảnh nhỏ).
 * value = danh sách ảnh đã tải xong, đúng thứ tự hiển thị; ids gửi kèm khi bấm Gửi / Lưu cơ hội.
 */
export default function ImageUploader({ value, onChange }: { value: PartnerImage[]; onChange: (v: PartnerImage[]) => void }) {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [busy, setBusy] = useState(0);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const latest = useRef(value);
  latest.current = value;

  useEffect(() => {
    papi.get<Cfg>("/attachments/config").then(setCfg, () => setCfg(null));
  }, []);

  if (!cfg) return null;
  if (!cfg.enabled) return <p className="muted" style={{ fontSize: 12.5 }}>Chưa mở tải ảnh lên — dán link ảnh (Google Drive…) vào ô Tài liệu, link chứng minh.</p>;

  async function uploadOne(file: File): Promise<PartnerImage> {
    const init = await papi.post<{ id: number; upload_url: string; content_type: string }>("/attachments/init", { filename: file.name, size: file.size });
    const put = await fetch(init.upload_url, { method: "PUT", body: file, headers: { "Content-Type": init.content_type } });
    if (!put.ok) throw new Error(`Tải ảnh ${file.name} lên không thành công (HTTP ${put.status}).`);
    return papi.post<PartnerImage>(`/attachments/${init.id}/complete`);
  }

  async function onFiles(files: FileList | null) {
    if (!files?.length || !cfg) return;
    setError("");
    const room = cfg.max_files - latest.current.length;
    const list = Array.from(files).slice(0, Math.max(0, room));
    if (files.length > room) setError(`Mỗi cơ hội tối đa ${cfg.max_files} ảnh.`);
    for (const f of list) {
      if (f.size > cfg.max_mb * 1024 * 1024) {
        setError(`${f.name}: ảnh tối đa ${cfg.max_mb} MB.`);
        continue;
      }
      setBusy((n) => n + 1);
      try {
        const img = await uploadOne(f);
        onChange([...latest.current, img]);
      } catch (e) {
        setError(e instanceof Error && !("status" in e) ? e.message : errMsg(e));
      } finally {
        setBusy((n) => n - 1);
      }
    }
    if (input.current) input.current.value = "";
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div className="ptn-images">
        {value.map((img, i) => (
          <figure key={img.id}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img.thumb_url ?? img.url ?? ""} alt={img.filename} />
            <button type="button" aria-label={`Bỏ ảnh ${img.filename}`} onClick={() => onChange(value.filter((x) => x.id !== img.id))}>×</button>
            {i === 0 ? <figcaption>Ảnh chính</figcaption> : null}
          </figure>
        ))}
        {value.length < cfg.max_files ? (
          <button type="button" className="ptn-image-add" onClick={() => input.current?.click()} disabled={busy > 0}>
            {busy ? "Đang tải…" : "+ Thêm ảnh"}
          </button>
        ) : null}
      </div>
      <input ref={input} type="file" accept={cfg.types.map((t) => `.${t}`).join(",")} multiple hidden onChange={(e) => onFiles(e.target.files)} />
      <span className="muted" style={{ fontSize: 12.5 }}>
        Tối đa {cfg.max_files} ảnh, mỗi ảnh ≤ {cfg.max_mb} MB ({cfg.types.join(", ")}). Ảnh chụp thông báo mời thầu, bảng nhu cầu, công trường… Không gửi ảnh giấy tờ cá nhân.
        Vị trí GPS trong ảnh được xoá tự động.
      </span>
      {error ? <span className="adm-err">{error}</span> : null}
    </div>
  );
}

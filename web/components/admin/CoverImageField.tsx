"use client";

import { type ChangeEvent, type DragEvent, useRef, useState } from "react";

import { putToR2 } from "@/components/admin/AttachmentsEditor";
import { api, errMsg } from "@/lib/admin/api";

import { Field, Icon } from "./ui";

const ACCEPT = "image/jpeg,image/png,image/webp";

/** Ảnh bìa (banner) bài tuyển dụng: chọn / kéo-thả ảnh → tải thẳng lên Cloudflare R2 → lưu đường dẫn công khai.
 *  Vẫn cho dán đường dẫn sẵn có (vd ảnh trong web/public: /careers/ten-vi-tri.webp, hoặc URL https). */
export function CoverImageField({ value, error, onChange }: { value: string; error?: string; onChange: (url: string) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [over, setOver] = useState(false);
  const url = value.trim();

  async function upload(file: File) {
    setMsg("");
    setProgress(0);
    try {
      const init = await api.post<{ upload_id: string; upload_url: string; content_type: string }>("/jobs/covers/init", { filename: file.name, size: file.size });
      await putToR2(init.upload_url, file, init.content_type, setProgress);
      const done = await api.post<{ url: string }>(`/jobs/covers/${init.upload_id}/complete`);
      onChange(done.url);
    } catch (e) {
      setMsg(errMsg(e));
    } finally {
      setProgress(null);
    }
  }

  const pick = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) void upload(f);
  };
  const drop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void upload(f);
  };

  return (
    <Field label="Ảnh bìa (banner)" error={error || msg} full htmlFor="j-cover_image">
      <div className="job-cover">
        <div
          className={over ? "job-cover-box over" : "job-cover-box"}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={drop}
        >
          {url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt="Xem trước ảnh bìa" />
          ) : (
            <p>Kéo-thả ảnh vào đây hoặc bấm <b>Chọn ảnh</b>.<br />JPG, PNG, WebP · nên dùng tỉ lệ 16:9 (vd 1672×941). Ảnh hiện ở đầu bài, thẻ danh sách và khi chia sẻ link.</p>
          )}
          {progress !== null ? <div className="job-cover-prog" role="status">Đang tải lên… {progress}%</div> : null}
        </div>
        <div className="job-cover-actions">
          <button type="button" className="adm-btn sm" onClick={() => fileRef.current?.click()} disabled={progress !== null}>
            <Icon name="plus" size={14} /> {url ? "Đổi ảnh" : "Chọn ảnh"}
          </button>
          {url ? (
            <button type="button" className="adm-btn sm ghost danger" onClick={() => onChange("")} disabled={progress !== null}>
              <Icon name="trash" size={13} /> Bỏ ảnh bìa
            </button>
          ) : null}
          <input ref={fileRef} type="file" accept={ACCEPT} hidden onChange={pick} />
        </div>
        <input
          id="j-cover_image"
          className="adm-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={500}
          placeholder="Hoặc dán đường dẫn: /careers/ten-vi-tri.webp hoặc https://…"
          aria-invalid={!!error}
        />
      </div>
    </Field>
  );
}

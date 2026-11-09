"use client";

import { type DragEvent, useEffect, useRef, useState } from "react";

import { api, errMsg } from "@/lib/admin/api";
import { type AttachConfig, type Attachment, fmtBytes } from "@/lib/commerce";

import { Icon } from "./ui";

/** Một ô tệp trong form: tệp đã có (att) hoặc đang tải lên (file + tiến trình). */
export interface AttachItem {
  key: string;
  att?: Attachment; // đã tải lên xong (status ready)
  file?: File;
  preview?: string; // ảnh xem trước tại máy trong lúc tải
  progress: number; // 0–100
  error?: string;
  fresh: boolean; // tải lên trong lần soạn này (chưa thuộc phiếu)
  caption: string; // lưu cùng lúc với phiếu
}

const extOf = (name: string) => (name.includes(".") ? name.split(".").pop()!.toLowerCase() : "");

/** PUT tệp thẳng lên R2 bằng link ký sẵn (XHR để có tiến trình). */
function putToR2(url: string, file: File, contentType: string, onProgress: (p: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", contentType);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)); };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Kho lưu trữ từ chối tệp (mã ${xhr.status}).`)));
    xhr.onerror = () => reject(new Error("Mất kết nối khi tải tệp lên kho lưu trữ."));
    xhr.send(file);
  });
}

/** Ảnh & tài liệu của phiếu (phần mở khoá sau khi mua): kéo-thả, dán ảnh, chọn tệp; tải thẳng lên Cloudflare R2.
 *  Tệp chỉ gắn vào phiếu khi bấm lưu phiếu (form gửi attachment_ids theo đúng thứ tự trong danh sách). */
export function AttachmentsEditor({ initial, onChange }: { initial: Attachment[]; onChange: (items: AttachItem[]) => void }) {
  const [cfg, setCfg] = useState<AttachConfig | null>(null);
  const [items, setItems] = useState<AttachItem[]>(() => initial.map((a) => ({ key: `a${a.id}`, att: a, progress: 100, fresh: false, caption: a.caption })));
  const [drag, setDrag] = useState(false);
  const [notice, setNotice] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => { api.get<AttachConfig>("/attachments/config").then(setCfg, () => setCfg(null)); }, []);
  useEffect(() => { onChange(items); }, [items, onChange]);
  useEffect(() => () => itemsRef.current.forEach((i) => i.preview && URL.revokeObjectURL(i.preview)), []);

  const patch = (key: string, p: Partial<AttachItem>) => setItems((xs) => xs.map((x) => (x.key === key ? { ...x, ...p } : x)));

  async function upload(key: string, file: File) {
    patch(key, { error: undefined, progress: 0 });
    try {
      const init = await api.post<{ attachment: Attachment; upload_url: string; content_type: string }>("/attachments/init", { filename: file.name, size: file.size });
      await putToR2(init.upload_url, file, init.content_type, (p) => patch(key, { progress: Math.min(p, 99) }));
      const att = await api.post<Attachment>(`/attachments/${init.attachment.id}/complete`);
      patch(key, { att, progress: 100 });
    } catch (e) {
      patch(key, { error: e instanceof Error && !("status" in e) ? e.message : errMsg(e) });
    }
  }

  function addFiles(list: FileList | File[]) {
    if (!cfg?.configured) return;
    const files = Array.from(list);
    const room = cfg.max_files - itemsRef.current.length;
    const msgs: string[] = [];
    if (files.length > room) msgs.push(`Mỗi phiếu tối đa ${cfg.max_files} tệp — bỏ qua ${files.length - Math.max(room, 0)} tệp.`);
    const add: AttachItem[] = [];
    for (const f of files.slice(0, Math.max(room, 0))) {
      const ext = extOf(f.name);
      const isImg = cfg.image_exts.includes(ext);
      if (!isImg && !cfg.file_exts.includes(ext)) { msgs.push(`“${f.name}”: không hỗ trợ loại tệp này.`); continue; }
      const max = (isImg ? cfg.image_max_mb : cfg.file_max_mb) * 1024 * 1024;
      if (f.size > max) { msgs.push(`“${f.name}”: vượt ${isImg ? cfg.image_max_mb : cfg.file_max_mb} MB.`); continue; }
      add.push({ key: `n${Date.now()}-${Math.random().toString(36).slice(2)}`, file: f, preview: isImg ? URL.createObjectURL(f) : undefined, progress: 0, fresh: true, caption: "" });
    }
    setNotice(msgs.join(" "));
    if (!add.length) return;
    setItems((xs) => [...xs, ...add]);
    add.forEach((it) => void upload(it.key, it.file!));
  }

  // Dán ảnh chụp màn hình (Ctrl+V) ở bất kỳ đâu trên trang, trừ khi đang gõ trong ô nhập
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const files = Array.from(e.clipboardData?.files ?? []);
      if (!files.length) return;
      e.preventDefault();
      addFiles(files.map((f, i) => (f.name && f.name !== "image.png" ? f : new File([f], `anh-dan-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}${i ? `-${i}` : ""}.png`, { type: f.type }))));
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  });

  function remove(it: AttachItem) {
    if (it.preview) URL.revokeObjectURL(it.preview);
    setItems((xs) => xs.filter((x) => x.key !== it.key));
    // tệp vừa tải trong lần soạn này → huỷ luôn trên kho; tệp đã thuộc phiếu sẽ bị gỡ khi lưu phiếu
    if (it.fresh && it.att) void api.del(`/attachments/${it.att.id}`).catch(() => {});
  }

  function move(it: AttachItem, d: -1 | 1) {
    setItems((xs) => {
      const i = xs.findIndex((x) => x.key === it.key);
      const j = i + d;
      if (i < 0 || j < 0 || j >= xs.length) return xs;
      const ys = [...xs];
      [ys[i], ys[j]] = [ys[j], ys[i]];
      return ys;
    });
  }

  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files); };

  if (cfg && !cfg.configured) {
    return (
      <div className="at-off">
        <Icon name="lock" size={16} />
        <span>Chưa cấu hình lưu trữ tệp (Cloudflare R2) nên chưa gắn được ảnh/tài liệu. Đặt các biến <code>LEADSCAN_R2_*</code> trong <code>.env</code> rồi khởi động lại API.</span>
      </div>
    );
  }

  return (
    <div className="at-editor">
      <div
        className={drag ? "at-drop on" : "at-drop"}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
      >
        <Icon name="plus" size={20} />
        <div>
          <b>Kéo thả ảnh / tài liệu vào đây</b>, dán ảnh (Ctrl+V) hoặc{" "}
          <button type="button" className="at-pick" onClick={() => inputRef.current?.click()} disabled={!cfg}>chọn tệp</button>
          <small>
            {cfg ? <>Ảnh {cfg.image_exts.join(", ")} ≤ {cfg.image_max_mb} MB · Tài liệu {cfg.file_exts.join(", ")} ≤ {cfg.file_max_mb} MB · tối đa {cfg.max_files} tệp</> : "Đang tải cấu hình…"}
          </small>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept={cfg ? [...cfg.image_exts, ...cfg.file_exts].map((x) => `.${x}`).join(",") : undefined}
          onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ""; }}
        />
      </div>
      {notice ? <div className="adm-alert" role="status" style={{ margin: 0 }}>{notice}</div> : null}

      {items.length ? (
        <ul className="at-grid">
          {items.map((it, idx) => {
            const name = it.att?.filename ?? it.file?.name ?? "";
            const isImg = it.att ? it.att.kind === "image" : !!it.preview;
            const src = it.att?.thumb_url ?? it.preview;
            const busy = !it.att && !it.error;
            return (
              <li key={it.key} className={it.error ? "at-tile err" : "at-tile"}>
                <div className="at-media">
                  {isImg && src ? <img src={src} alt={it.att?.caption || name} loading="lazy" /> : <span className="at-ext">{extOf(name).toUpperCase() || "TỆP"}</span>}
                  {busy ? (
                    <div className="at-progress" role="progressbar" aria-valuenow={it.progress} aria-valuemin={0} aria-valuemax={100} aria-label={`Đang tải ${name}`}>
                      <i style={{ width: `${it.progress}%` }} />
                      <span>{it.progress < 100 ? `Đang tải ${it.progress}%` : "Đang xử lý…"}</span>
                    </div>
                  ) : null}
                  {it.error ? (
                    <div className="at-fail">
                      <span>{it.error}</span>
                      {it.file ? <button type="button" className="adm-btn sm" onClick={() => void upload(it.key, it.file!)}>Thử lại</button> : null}
                    </div>
                  ) : null}
                  {idx === 0 && isImg && it.att ? <span className="at-first">Ảnh đầu</span> : null}
                </div>
                <div className="at-info">
                  <span className="at-name" title={name}>{name}</span>
                  <span className="muted">{fmtBytes(it.att?.size ?? it.file?.size ?? 0)}</span>
                </div>
                {it.att ? (
                  <input
                    className="adm-input at-cap"
                    value={it.caption}
                    maxLength={300}
                    placeholder="Chú thích (không bắt buộc)"
                    aria-label={`Chú thích cho ${name}`}
                    onChange={(e) => patch(it.key, { caption: e.target.value })}
                  />
                ) : null}
                <div className="at-act">
                  <button type="button" className="adm-btn sm ghost" onClick={() => move(it, -1)} disabled={idx === 0} aria-label="Đưa lên trước">←</button>
                  <button type="button" className="adm-btn sm ghost" onClick={() => move(it, 1)} disabled={idx === items.length - 1} aria-label="Đưa xuống sau">→</button>
                  {it.att?.download_url ? <a className="adm-btn sm ghost" href={it.att.download_url} aria-label={`Tải ${name}`}><Icon name="external" size={13} /></a> : null}
                  <button type="button" className="adm-btn sm ghost danger" onClick={() => remove(it)} aria-label={`Bỏ ${name}`}><Icon name="trash" size={13} /></button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

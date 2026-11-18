"use client";

import "@/components/cam-nang/article-preview.css";

import { type FormEvent, useEffect, useMemo, useState } from "react";

import ArticleBody from "@/components/cam-nang/ArticleBody";
import { AREA_PAGES } from "@/lib/areas";
import { api, errFields, errMsg } from "@/lib/admin/api";
import { ARTICLE_STATUS, type ArticleAdmin, type ArticleSection, articleToc, DEFAULT_SECTION, plain, sectionHref, slugify } from "@/lib/blog";

import { CoverImageField } from "./CoverImageField";
import { Field, Icon } from "./ui";

type Values = Record<string, string>;
const KEYS = ["title", "slug", "section_id", "status", "seo_title", "excerpt", "category", "area", "cover_image", "body", "author_name", "published_at"] as const;

const TEMPLATE = [
  "Mở đầu 2–3 câu: người đọc gặp vấn đề gì, bài này giúp gì.",
  "",
  "## Vấn đề / bối cảnh",
  "Giải thích ngắn, có ví dụ thực tế.",
  "",
  "## Cách làm từng bước",
  "1. Bước thứ nhất",
  "2. Bước thứ hai",
  "3. Bước thứ ba",
  "",
  "> Mẹo: một lưu ý quan trọng người đọc hay bỏ qua.",
  "",
  "## Ví dụ",
  "- …",
  "",
  "## Kết luận",
  "Tóm tắt 2–3 ý, mời người đọc [xem cơ hội đang mở](/co-hoi) hoặc [đăng ký đối tác](/doi-tac).",
].join("\n");

/** Phát sự kiện này sau khi thêm / sửa / xoá danh mục hoặc bài → menu "Bài viết" tải lại danh mục và số bài */
export const SECTIONS_CHANGED = "ls:article-sections-changed";
export const notifySectionsChanged = () => window.dispatchEvent(new Event(SECTIONS_CHANGED));

export interface ArticleMeta {
  sections: ArticleSection[];
  topics: Record<string, string[]>;
}

/** Danh mục + chủ đề gợi ý cho trang danh sách / soạn bài */
export function useArticleMeta(): ArticleMeta {
  const [m, setM] = useState<ArticleMeta>({ sections: [], topics: {} });
  useEffect(() => {
    api.get<ArticleMeta>("/articles/meta").then(setM, () => {});
  }, []);
  return m;
}

/** Nhãn trạng thái: Đang hiện / Hẹn giờ / Bản nháp */
export function liveBadge(a: { is_live: boolean; status: string }) {
  const cls = a.is_live ? "s-active" : a.status === "published" ? "s-contacted" : "s-suspended";
  const label = a.is_live ? "Đang hiện" : a.status === "published" ? "Hẹn giờ" : ARTICLE_STATUS[a.status] ?? a.status;
  return <span className={`adm-badge ${cls}`}>{label}</span>;
}

/** ISO (UTC) ↔ ô datetime-local theo giờ máy người soạn */
const toLocal = (iso?: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

function initial(a?: ArticleAdmin, sectionId?: number): Values {
  const v: Values = {};
  for (const k of KEYS) v[k] = k === "published_at" ? toLocal(a?.published_at) : String(a?.[k as keyof ArticleAdmin] ?? "");
  v.status ||= "draft";
  if (!v.section_id && sectionId) v.section_id = String(sectionId);
  return v;
}

const words = (s: string) => (plain(s).match(/[\p{L}\p{N}]+/gu) ?? []).length;

export function ArticleForm({
  initialValue, sections, topics, defaultSectionId, onSubmit, submitLabel,
}: {
  initialValue?: ArticleAdmin;
  sections: ArticleSection[];
  topics: Record<string, string[]>; // chủ đề gợi ý theo id danh mục
  defaultSectionId?: number; // bài mới: danh mục đang lọc ở danh sách
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
  submitLabel: string;
}) {
  const [v, setV] = useState<Values>(() => initial(initialValue, defaultSectionId));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);

  const set = (k: string) => (e: { target: { value: string } }) => {
    const val = e.target.value;
    setV((s) => ({ ...s, [k]: val }));
    if (errors[k]) setErrors(({ [k]: _, ...rest }) => rest);
  };

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setMsg("");
    try {
      await onSubmit({ ...v, section_id: v.section_id ? Number(v.section_id) : null, published_at: v.published_at ? new Date(v.published_at).toISOString() : null });
    } catch (err) {
      setMsg(errMsg(err));
      setErrors(errFields(err));
    } finally {
      setBusy(false);
    }
  }

  // Danh mục chưa tải xong / bài cũ chưa có danh mục → coi như Cẩm nang
  const section = sections.find((x) => String(x.id) === v.section_id) ?? sections.find((x) => x.slug === DEFAULT_SECTION);
  const isGuide = !section || section.slug === DEFAULT_SECTION;
  const base = sectionHref(section?.slug ?? DEFAULT_SECTION); // "/cam-nang" | "/bai-viet/tuyen-dung"
  const topicList = [...new Set([...(topics[v.section_id] ?? []), ...(v.category ? [v.category] : [])])];
  const seoTitle = `${v.seo_title || v.title || "Tiêu đề bài viết"} | ${section?.name ?? "Cẩm nang"} LeadScan`;
  const slug = v.slug || slugify(v.title) || "duong-dan-bai-viet";
  const n = words(v.body);
  const h2 = articleToc(v.body).length;
  const checks = useMemo(() => {
    const t = (v.seo_title || v.title).length;
    return [
      [t >= 30 && t <= 65, `Tiêu đề hiện trên Google 30–65 ký tự (đang ${t})`],
      [v.excerpt.length >= 70 && v.excerpt.length <= 160, `Mô tả ngắn 70–160 ký tự (đang ${v.excerpt.length})`],
      [n >= 600, `Nội dung từ 600 chữ (đang ${n})`],
      [h2 >= 2, `Có ít nhất 2 tiêu đề mục "## " (đang ${h2})`],
      [/\]\(\/(co-hoi|doi-tac|cam-nang|bai-viet|tuyen-dung|#dang-ky)/.test(v.body), "Có link nội bộ tới /co-hoi, /doi-tac hoặc bài viết khác"],
      [Boolean(v.cover_image), "Có ảnh bìa (hiện khi chia sẻ link)"],
      [Boolean(v.category), "Đã chọn chủ đề"],
      [!isGuide || !v.area || v.body.includes(`/co-hoi/khu-vuc/${v.area}`) || /\]\(\/co-hoi\/(khu-vuc|nganh)\//.test(v.body), "Bài theo khu vực nên link tới trang cơ hội của khu vực / ngành"],
    ] as [boolean, string][];
  }, [v, n, h2, isGuide]);

  const scheduled = v.status === "published" && v.published_at && new Date(v.published_at) > new Date();

  return (
    <form onSubmit={submit} noValidate className="adm-grid">
      {msg ? <div className="adm-alert">{msg}</div> : null}
      <div className="adm-grid side">
        <div className="adm-grid">
          <section className="adm-card">
            <div className="hd"><h2>Thông tin bài</h2></div>
            <div className="bd adm-form">
              <Field label="Tiêu đề bài *" error={errors.title} full htmlFor="a-title">
                <input id="a-title" className="adm-input" value={v.title} onChange={set("title")} maxLength={200} placeholder="VD: 7 cách tìm khách hàng B2B cho xưởng bao bì" aria-invalid={!!errors.title} />
              </Field>
              <Field label="Danh mục *" error={errors.section_id} htmlFor="a-section">
                <select id="a-section" className="adm-input" value={v.section_id} onChange={set("section_id")} aria-invalid={!!errors.section_id}>
                  {!sections.length ? <option value={v.section_id}>Đang tải…</option> : null}
                  {sections.map((x) => <option key={x.id} value={x.id}>{x.name}{x.is_active ? "" : " (đang ẩn)"}</option>)}
                </select>
              </Field>
              <Field label="Chủ đề" error={errors.category} htmlFor="a-cat">
                <input id="a-cat" className="adm-input" list="a-cat-list" value={v.category} onChange={set("category")} maxLength={80} placeholder={topicList.length ? "Chọn hoặc gõ chủ đề mới" : "Gõ chủ đề, vd: Văn hoá công ty"} />
                <datalist id="a-cat-list">{topicList.map((c) => <option key={c} value={c} />)}</datalist>
              </Field>
              <Field label="Đường dẫn" error={errors.slug} full htmlFor="a-slug">
                <div className="job-slug"><span>{base}/</span><input id="a-slug" className="adm-input" value={v.slug} onChange={set("slug")} maxLength={160} placeholder="Để trống = tự tạo từ tiêu đề" /></div>
              </Field>
              <Field label="Mô tả ngắn (hiện trên Google & thẻ danh sách)" error={errors.excerpt} full htmlFor="a-excerpt">
                <textarea id="a-excerpt" className="adm-input" value={v.excerpt} onChange={set("excerpt")} maxLength={400} style={{ minHeight: 70 }} placeholder="1–2 câu tóm ý chính, có từ khoá người đọc hay tìm" />
              </Field>
              {isGuide || v.area ? (
              <Field label="Khu vực (tỉnh / miền)" error={errors.area} htmlFor="a-area">
                <select id="a-area" className="adm-input" value={v.area} onChange={set("area")}>
                  <option value="">— Bài chung, không gắn khu vực —</option>
                  <optgroup label="Miền">{AREA_PAGES.filter((x) => x.kind === "region").map((x) => <option key={x.slug} value={x.slug}>{x.name}</option>)}</optgroup>
                  <optgroup label="Tỉnh / thành">{AREA_PAGES.filter((x) => x.kind === "province").map((x) => <option key={x.slug} value={x.slug}>{x.name}</option>)}</optgroup>
                </select>
              </Field>
              ) : null}
              <Field label="Tác giả" error={errors.author_name} htmlFor="a-author">
                <input id="a-author" className="adm-input" value={v.author_name} onChange={set("author_name")} maxLength={120} placeholder="Để trống = LeadScan" />
              </Field>
              <CoverImageField
                value={v.cover_image}
                error={errors.cover_image}
                endpoint="/articles/covers"
                id="a-cover_image"
                hint="JPG, PNG, WebP · tỉ lệ 16:9 (vd 1600×900). Hiện ở đầu bài, thẻ danh sách và khi chia sẻ link."
                placeholder="Hoặc dán đường dẫn ảnh https://…"
                onChange={(url) => {
                  setV((s) => ({ ...s, cover_image: url }));
                  if (errors.cover_image) setErrors(({ cover_image: _, ...rest }) => rest);
                }}
              />
            </div>
          </section>

          <section className="adm-card">
            <div className="hd">
              <div><h2>Nội dung</h2><p className="muted" style={{ fontSize: 12.5 }}>{n} chữ · khoảng {Math.max(1, Math.ceil(n / 220))} phút đọc</p></div>
              <div className="adm-actions">
                {!v.body.trim() ? <button type="button" className="adm-btn sm" onClick={() => setV((s) => ({ ...s, body: TEMPLATE }))}><Icon name="spark" size={14} /> Dùng khung bài</button> : null}
                <div className="job-seg" role="tablist" aria-label="Chế độ xem">
                  <button type="button" role="tab" aria-selected={!preview} className={!preview ? "on" : undefined} onClick={() => setPreview(false)}>Soạn</button>
                  <button type="button" role="tab" aria-selected={preview} className={preview ? "on" : undefined} onClick={() => setPreview(true)}>Xem trước</button>
                </div>
              </div>
            </div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              {preview ? (
                <div className="art-prev">
                  <h1>{v.title || "Tiêu đề bài viết"}</h1>
                  {v.excerpt ? <p className="lead">{v.excerpt}</p> : null}
                  {v.body.trim() ? <ArticleBody text={v.body} /> : <p className="muted">Chưa có nội dung.</p>}
                </div>
              ) : (
                <>
                  <div className="job-hint">
                    <b>Định dạng:</b> <code>## </code> tiêu đề mục (vào mục lục) · <code>### </code> tiêu đề nhỏ · <code>- </code> gạch đầu dòng · <code>1. </code> đánh số ·{" "}
                    <code>&gt; </code> lưu ý · <code>**đậm**</code> · <code>[chữ](/co-hoi)</code> link · <code>![mô tả](https://…/anh.jpg)</code> ảnh · dòng trống = đoạn mới.
                  </div>
                  <textarea
                    id="a-body" className="adm-input" value={v.body} onChange={set("body")} maxLength={100000}
                    style={{ minHeight: 520, fontFamily: "ui-monospace, Consolas, monospace", fontSize: 13.5, lineHeight: 1.6 }}
                    aria-label="Nội dung bài" aria-invalid={!!errors.body}
                  />
                  {errors.body ? <span className="adm-err">{errors.body}</span> : null}
                </>
              )}
            </div>
          </section>
        </div>

        <div className="adm-grid" style={{ position: "sticky", top: 16, alignSelf: "start" }}>
          <section className="adm-card">
            <div className="hd"><h2>Đăng bài</h2></div>
            <div className="bd" style={{ display: "grid", gap: 14 }}>
              <Field label="Trạng thái" error={errors.status} htmlFor="a-status">
                <select id="a-status" className="adm-input" value={v.status} onChange={set("status")}>
                  {Object.entries(ARTICLE_STATUS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </Field>
              <Field label="Ngày đăng" error={errors.published_at} htmlFor="a-date">
                <input id="a-date" className="adm-input" type="datetime-local" value={v.published_at} onChange={set("published_at")} />
              </Field>
              <p className="muted" style={{ fontSize: 12.5, marginTop: -6 }}>
                {section && !section.is_active ? `Danh mục “${section.name}” đang ẩn — bài chưa hiện công khai dù đã đăng.`
                  : v.status === "draft" ? `Bản nháp chưa hiện trên ${base}.`
                    : scheduled ? "Hẹn giờ: bài tự hiện khi tới ngày đăng."
                      : `Hiện trên ${base} ngay khi lưu. Để trống ngày = đăng bây giờ.`}
              </p>
              <button className="adm-btn primary" type="submit" disabled={busy}>{busy ? "Đang lưu…" : submitLabel}</button>
            </div>
          </section>

          <section className="adm-card">
            <div className="hd"><h2>Trên Google</h2></div>
            <div className="bd" style={{ display: "grid", gap: 12 }}>
              <div className="serp">
                <span className="u">leadscan.net › {base.slice(1).split("/").join(" › ")} › {slug}</span>
                <b>{seoTitle.length > 70 ? `${seoTitle.slice(0, 68)}…` : seoTitle}</b>
                <p>{v.excerpt ? (v.excerpt.length > 160 ? `${v.excerpt.slice(0, 158)}…` : v.excerpt) : "Mô tả ngắn sẽ hiện ở đây."}</p>
              </div>
              <Field label="Tiêu đề SEO (không bắt buộc)" error={errors.seo_title} htmlFor="a-seo">
                <input id="a-seo" className="adm-input" value={v.seo_title} onChange={set("seo_title")} maxLength={200} placeholder="Để trống = dùng tiêu đề bài" />
              </Field>
              <ul className="seo-checks">
                {checks.map(([ok, t]) => <li key={t} className={ok ? "ok" : undefined}><Icon name={ok ? "check" : "flag"} size={14} />{t}</li>)}
              </ul>
            </div>
          </section>
        </div>
      </div>
    </form>
  );
}

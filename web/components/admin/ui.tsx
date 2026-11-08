"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";

const ICONS: Record<string, ReactNode> = {
  scan: <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10" />,
  home: <path d="M3 10.5 12 3l9 7.5V21H3z" />,
  building: <><rect x="4" y="3" width="16" height="18" rx="1" /><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6" /></>,
  key: <><circle cx="8" cy="15" r="4" /><path d="m10.8 12.2 9.2-9.2M17 6l3 3M14 9l2 2" /></>,
  logout: <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />,
  search: <><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  plus: <path d="M12 5v14M5 12h14" />,
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  note: <path d="M4 4h16v12H8l-4 4z" />,
  flag: <path d="M4 21V4h11l-1 4h6v8H9l1-4H4" />,
  edit: <path d="M4 20h4L19 9l-4-4L4 16zM14 6l4 4" />,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  spark: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  trash: <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />,
  external: <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />,
  ticket: <path d="M3 9V7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a3 3 0 0 0 0 6v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a3 3 0 0 0 0-6zM13 5v2M13 11v2M13 17v2" />,
  wallet: <path d="M20 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h15v14H5a2 2 0 0 1-2-2V5M16 14h.01" />,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>,
  lock: <><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>,
  check: <path d="M20 6 9 17l-5-5" />,
  copy: <><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" /></>,
  receipt: <path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2zM9 8h6M9 12h6M9 16h3" />,
  card: <><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20M6 15h4" /></>,
  phone: <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z" />,
  mail: <><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 6-10 7L2 6" /></>,
  factory: <path d="M2 20V9l6 4V9l6 4V4h4l2 16zM2 20h20" />,
  map: <><path d="M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z" /><circle cx="12" cy="9" r="2.5" /></>,
  gauge: <><path d="M12 14l4-4M3.3 17a9 9 0 1 1 17.4 0" /><circle cx="12" cy="14" r="1.5" /></>,
  layers: <path d="M12 2 2 7l10 5 10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />,
  bookmark: <path d="M6 3h12v18l-6-4-6 4z" />,
};

export function Icon({ name, size }: { name: keyof typeof ICONS | string; size?: number }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true" style={size ? { width: size, height: size } : undefined}>
      {ICONS[name]}
    </svg>
  );
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <span className={`adm-badge s-${status}`}>{label ?? status}</span>;
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts.at(-2)?.[0] ?? "") + (parts.at(-1)?.[0] ?? "")).toUpperCase() || "?";
}

export function Field({
  label,
  error,
  children,
  full,
  htmlFor,
}: {
  label: string;
  error?: string;
  children: ReactNode;
  full?: boolean;
  htmlFor?: string;
}) {
  return (
    <div className={full ? "adm-field full" : "adm-field"}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {error ? <span className="adm-err">{error}</span> : null}
    </div>
  );
}

/** Hộp thoại dùng <dialog> gốc của trình duyệt (có sẵn Esc, khoá focus). */
export function Dialog({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="adm-dialog" onClose={onClose} onCancel={onClose}>
      <div className="hd"><h2>{title}</h2></div>
      <div className="bd">{children}</div>
      {footer ? <div className="ft adm-actions">{footer}</div> : null}
    </dialog>
  );
}

export function Skeleton({ h = 16, w = "100%" }: { h?: number; w?: number | string }) {
  return <div className="adm-skel" style={{ height: h, width: w }} />;
}

export function ScoreChip({ score }: { score: number }) {
  const cls = score >= 85 ? "sc-hi" : score >= 70 ? "sc-md" : "sc-lo";
  return (
    <span className={`adm-score ${cls}`} title="Điểm chất lượng AI (0–100)">
      {score}
      <small>điểm</small>
    </span>
  );
}

/** Nút sao chép nhanh (số tài khoản, nội dung chuyển khoản) */
export function CopyField({ label, value }: { label: string; value: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="adm-field">
      <span className="lbl">{label}</span>
      <div className="adm-copy">
        <b>{value}</b>
        <button
          type="button"
          className="adm-btn sm ghost"
          onClick={() => navigator.clipboard?.writeText(value).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); })}
          aria-label={`Sao chép ${label}`}
        >
          <Icon name={done ? "check" : "copy"} size={14} /> {done ? "Đã chép" : "Chép"}
        </button>
      </div>
    </div>
  );
}

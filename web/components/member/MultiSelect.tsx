"use client";

import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/admin/ui";

/** Bỏ dấu tiếng Việt để gõ "bac ninh" vẫn tìm được "Bắc Ninh" */
export function fold(s: string) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase().trim();
}

/**
 * Ô chọn nhiều có tìm kiếm: gõ để lọc, danh sách sổ xuống, chọn xong thành thẻ trong ô.
 * Bàn phím: ↑/↓ chọn dòng, Enter thêm, Backspace (ô trống) xoá thẻ cuối, Esc đóng.
 */
export function MultiSelect({
  icon,
  label,
  options,
  value,
  onChange,
  placeholder = "Gõ để tìm…",
  allowCustom = false,
  maxLength = 60,
}: {
  icon: string;
  label: string;
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  allowCustom?: boolean;
  maxLength?: number;
}) {
  const id = useId();
  const listId = `${id}-list`;
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = useMemo(() => {
    const f = fold(q);
    return options.filter((o) => !value.includes(o) && (!f || fold(o).includes(f)));
  }, [options, value, q]);
  const custom = allowCustom && q.trim() && ![...options, ...value].some((o) => fold(o) === fold(q)) ? q.trim() : "";
  const rows = custom ? [...matches, custom] : matches;

  useEffect(() => setActive(0), [q, open]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  useEffect(() => {
    if (open) document.getElementById(`${id}-opt-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, open, id]);

  function add(v: string) {
    if (!v || value.includes(v)) return;
    onChange([...value, v]);
    setQ("");
    inputRef.current?.focus();
  }
  const remove = (v: string) => onChange(value.filter((x) => x !== v));

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, Math.max(rows.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (open && rows[active]) add(rows[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Backspace" && !q && value.length) {
      remove(value[value.length - 1]);
    }
  }

  return (
    <div className="mt-group" ref={boxRef}>
      <label className="mt-label" htmlFor={`${id}-input`}>
        <Icon name={icon} />{label}{value.length ? <small>{value.length} đã chọn</small> : null}
      </label>
      <div className={open ? "ms-box open" : "ms-box"} onClick={() => { inputRef.current?.focus(); setOpen(true); }}>
        {value.map((v) => (
          <span className="ms-tag" key={v}>
            {v}
            <button type="button" aria-label={`Bỏ ${v}`} onClick={(e) => { e.stopPropagation(); remove(v); }}>×</button>
          </span>
        ))}
        <input
          ref={inputRef}
          id={`${id}-input`}
          className="ms-input"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && rows[active] ? `${id}-opt-${active}` : undefined}
          value={q}
          maxLength={maxLength}
          placeholder={value.length ? "" : placeholder}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
        />
        <Icon name="search" size={15} />
      </div>
      {open ? (
        <ul className="ms-list" id={listId} role="listbox" aria-label={label}>
          {rows.length ? rows.map((o, i) => (
            <li
              key={o}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? "on" : undefined}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => { e.preventDefault(); add(o); }}
            >
              {o === custom ? <>Thêm “<b>{o}</b>”</> : o}
            </li>
          )) : (
            <li className="ms-empty" aria-disabled="true">{value.length && !q ? "Đã chọn hết" : "Không có lựa chọn phù hợp"}</li>
          )}
        </ul>
      ) : null}
    </div>
  );
}

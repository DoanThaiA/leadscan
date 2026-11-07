"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useAdmin } from "@/components/admin/AdminContext";
import { Dialog, Field, Icon, initials, Skeleton } from "@/components/admin/ui";
import { api, ApiError } from "@/lib/admin/api";
import { fmtDateTime, fromNow } from "@/lib/admin/format";
import type { Role, User } from "@/lib/admin/types";

type Errors = Record<string, string>;

export default function StaffPage() {
  const { user: me, meta, reloadMeta } = useAdmin();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [resetFor, setResetFor] = useState<User | null>(null);

  const load = useCallback(() => {
    api.get<User[]>("/users").then(setUsers, (e) => setError(e.message));
  }, []);

  useEffect(() => {
    document.title = "Nhân viên · Quản trị LeadScan";
    load();
  }, [load]);

  async function update(u: User, body: Partial<{ role: Role; is_active: boolean }>) {
    try {
      await api.patch(`/users/${u.id}`, body);
      load();
      reloadMeta();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Không cập nhật được.");
    }
  }

  if (me.role !== "admin") {
    return <div className="adm-card adm-empty">Chỉ quản trị viên được quản lý nhân viên.</div>;
  }

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Nhân viên</h1>
          <p>Tài khoản đăng nhập trang quản trị. Nhân viên xem và chăm sóc khách hàng; quản trị viên thêm quản lý tài khoản và xoá khách hàng.</p>
        </div>
        <button className="adm-btn primary" onClick={() => setCreating(true)}><Icon name="plus" size={16} /> Thêm nhân viên</button>
      </div>

      {error ? <div className="adm-alert" style={{ marginBottom: 16 }}>{error}</div> : null}

      <section className="adm-card">
        {!users ? (
          <div className="bd" style={{ display: "grid", gap: 12 }}>{[1, 2, 3].map((i) => <Skeleton key={i} h={22} />)}</div>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr><th>Nhân viên</th><th>Vai trò</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th style={{ textAlign: "right" }}>Thao tác</th></tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const self = u.id === me.id;
                  return (
                    <tr key={u.id}>
                      <td>
                        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                          <span className="adm-avatar">{initials(u.full_name)}</span>
                          <div>
                            <div className="name">{u.full_name}{self ? <span className="muted" style={{ fontWeight: 400 }}> (bạn)</span> : null}</div>
                            <div className="sub">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <select className="adm-input" style={{ width: 130, height: 32 }} value={u.role} disabled={self} onChange={(e) => update(u, { role: e.target.value as Role })} aria-label={`Vai trò của ${u.full_name}`}>
                          {Object.entries(meta.roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                        </select>
                      </td>
                      <td>
                        {u.is_active ? <span className="adm-badge s-active">Đang hoạt động</span> : <span className="adm-badge s-suspended">Đã khoá</span>}
                      </td>
                      <td title={fmtDateTime(u.last_login_at)}>{u.last_login_at ? fromNow(u.last_login_at) : <span className="muted">Chưa đăng nhập</span>}</td>
                      <td>
                        <div className="adm-actions">
                          <button className="adm-btn sm" onClick={() => setResetFor(u)}>Đặt lại mật khẩu</button>
                          {!self ? (
                            <button className={u.is_active ? "adm-btn sm danger" : "adm-btn sm"} onClick={() => update(u, { is_active: !u.is_active })}>
                              {u.is_active ? "Khoá" : "Mở khoá"}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <CreateUserDialog open={creating} onClose={() => setCreating(false)} onCreated={() => { setCreating(false); load(); reloadMeta(); }} roles={meta.roles} />
      <ResetPasswordDialog user={resetFor} onClose={() => setResetFor(null)} />
    </>
  );
}

function CreateUserDialog({ open, onClose, onCreated, roles }: { open: boolean; onClose: () => void; onCreated: () => void; roles: Record<string, string> }) {
  const [errors, setErrors] = useState<Errors>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<string, string>;
    setBusy(true);
    setErrors({});
    setMsg("");
    try {
      await api.post("/users", f);
      (e.target as HTMLFormElement).reset();
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) {
        setMsg(err.message);
        setErrors(err.fields);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} title="Thêm nhân viên" onClose={onClose}>
      {open ? (
        <form className="adm-form" onSubmit={submit} noValidate>
          {msg ? <div className="adm-alert full">{msg}</div> : null}
          <Field label="Họ và tên" error={errors.full_name} full htmlFor="u-name">
            <input id="u-name" className="adm-input" name="full_name" maxLength={100} autoFocus aria-invalid={!!errors.full_name} />
          </Field>
          <Field label="Email đăng nhập" error={errors.email} full htmlFor="u-email">
            <input id="u-email" className="adm-input" name="email" type="email" maxLength={150} autoComplete="off" aria-invalid={!!errors.email} />
          </Field>
          <Field label="Vai trò" error={errors.role} htmlFor="u-role">
            <select id="u-role" className="adm-input" name="role" defaultValue="staff">
              {Object.entries(roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <Field label="Mật khẩu ban đầu (≥ 10 ký tự)" error={errors.password} htmlFor="u-pw">
            <input id="u-pw" className="adm-input" name="password" type="password" minLength={10} autoComplete="new-password" aria-invalid={!!errors.password} />
          </Field>
          <p className="muted full" style={{ fontSize: 12.5 }}>Gửi mật khẩu cho nhân viên qua kênh riêng và nhắc họ đổi ở mục “Tài khoản của tôi”.</p>
          <div className="adm-actions full">
            <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
            <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang tạo…" : "Tạo tài khoản"}</button>
          </div>
        </form>
      ) : null}
    </Dialog>
  );
}

function ResetPasswordDialog({ user, onClose }: { user: User | null; onClose: () => void }) {
  const [msg, setMsg] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setMsg("");
    setDone(false);
  }, [user]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!user) return;
    const pw = String(new FormData(e.currentTarget).get("password") ?? "");
    setBusy(true);
    setMsg("");
    try {
      await api.patch(`/users/${user.id}`, { password: pw });
      setDone(true);
    } catch (err) {
      setMsg(err instanceof ApiError ? err.fields.password ?? err.message : "Không đặt lại được.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={user !== null} title={`Đặt lại mật khẩu — ${user?.full_name ?? ""}`} onClose={onClose}>
      {user ? (
        done ? (
          <>
            <div className="adm-alert ok">Đã đặt mật khẩu mới. {user.full_name} đã bị đăng xuất khỏi mọi thiết bị.</div>
            <div className="adm-actions"><button className="adm-btn primary" onClick={onClose}>Xong</button></div>
          </>
        ) : (
          <form onSubmit={submit} style={{ display: "grid", gap: 14 }}>
            {msg ? <div className="adm-alert">{msg}</div> : null}
            <Field label="Mật khẩu mới (≥ 10 ký tự)" htmlFor="r-pw">
              <input id="r-pw" className="adm-input" name="password" type="password" minLength={10} autoComplete="new-password" autoFocus />
            </Field>
            <div className="adm-actions">
              <button type="button" className="adm-btn" onClick={onClose}>Huỷ</button>
              <button type="submit" className="adm-btn primary" disabled={busy}>{busy ? "Đang lưu…" : "Đặt mật khẩu"}</button>
            </div>
          </form>
        )
      ) : null}
    </Dialog>
  );
}

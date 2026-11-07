"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { api } from "@/lib/admin/api";
import type { Meta, User } from "@/lib/admin/types";

interface Ctx {
  user: User;
  meta: Meta;
  reloadMeta: () => Promise<void>;
}

const AdminCtx = createContext<Ctx | null>(null);

export function useAdmin(): Ctx {
  const v = useContext(AdminCtx);
  if (!v) throw new Error("useAdmin phải nằm trong AdminProvider");
  return v;
}

/** Tải người dùng hiện tại + danh mục; chưa đăng nhập thì api tự chuyển tới /admin/login. */
export function AdminProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);

  const reloadMeta = useCallback(async () => {
    setMeta(await api.get<Meta>("/meta"));
  }, []);

  useEffect(() => {
    let alive = true;
    Promise.all([api.get<User>("/auth/me"), api.get<Meta>("/meta")])
      .then(([u, m]) => {
        if (alive) {
          setUser(u);
          setMeta(m);
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (!user || !meta) return <>{fallback}</>;
  return <AdminCtx.Provider value={{ user, meta, reloadMeta }}>{children}</AdminCtx.Provider>;
}

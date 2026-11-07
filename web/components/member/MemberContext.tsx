"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { mapi } from "@/lib/member/api";

export interface MemberMe {
  id: number;
  email: string;
  full_name: string;
  company: {
    id: number;
    code: string;
    name: string;
    tax_code: string;
    address: string;
    status: string;
    points_balance: number;
    membership_expires_at: string | null;
    membership_active: boolean;
  };
}

interface Ctx {
  me: MemberMe;
  refresh: () => Promise<void>;
  setMe: (m: MemberMe) => void;
}

const MemberCtx = createContext<Ctx | null>(null);

export function useMember(): Ctx {
  const v = useContext(MemberCtx);
  if (!v) throw new Error("useMember phải nằm trong MemberProvider");
  return v;
}

export function MemberProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const [me, setMe] = useState<MemberMe | null>(null);
  const refresh = useCallback(async () => {
    setMe(await mapi.get<MemberMe>("/auth/me"));
  }, []);
  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);
  if (!me) return <>{fallback}</>;
  return <MemberCtx.Provider value={{ me, refresh, setMe }}>{children}</MemberCtx.Provider>;
}

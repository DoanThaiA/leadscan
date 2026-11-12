"use client";

import { useRouter } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { papi, type PartnerMe, type RewardConfig } from "@/lib/partner/api";
import { type Reward, rewardFrom } from "@/lib/partner/content";

interface Ctx {
  me: PartnerMe;
  reward: Reward;
  refresh: () => Promise<void>;
}

const PartnerCtx = createContext<Ctx | null>(null);

export function usePartner(): Ctx {
  const v = useContext(PartnerCtx);
  if (!v) throw new Error("usePartner phải nằm trong PartnerProvider");
  return v;
}

/** Tải đối tác đang đăng nhập + mức thưởng đang áp dụng. Chưa xác thực SĐT → chuyển sang bước nhập OTP. */
export function PartnerProvider({ children, fallback }: { children: ReactNode; fallback: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<PartnerMe | null>(null);
  const [reward, setReward] = useState<Reward>(rewardFrom(null));
  const refresh = useCallback(async () => {
    setMe(await papi.get<PartnerMe>("/auth/me"));
  }, []);
  useEffect(() => {
    refresh().catch(() => {});
    papi.get<RewardConfig>("/reward-config").then((c) => setReward(rewardFrom(c)), () => {});
  }, [refresh]);
  useEffect(() => {
    if (me && !me.phone_verified) router.replace("/doi-tac/xac-thuc");
  }, [me, router]);
  if (!me || !me.phone_verified) return <>{fallback}</>;
  return <PartnerCtx.Provider value={{ me, reward, refresh }}>{children}</PartnerCtx.Provider>;
}

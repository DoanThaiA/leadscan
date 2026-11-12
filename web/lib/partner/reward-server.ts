import type { RewardConfig } from "@/lib/partner/api";
import { type Reward, rewardFrom } from "@/lib/partner/content";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/** Mức thưởng đang áp dụng cho trang render phía máy chủ (landing, điều khoản). Lỗi API → mức mặc định. */
export async function getReward(): Promise<Reward> {
  try {
    const r = await fetch(`${API_INTERNAL_URL}/api/partner/reward-config`, { next: { revalidate: 300 } });
    if (!r.ok) return rewardFrom(null);
    return rewardFrom((await r.json()) as RewardConfig);
  } catch {
    return rewardFrom(null);
  }
}


import { headers } from "next/headers";

import { SITE_HEADER, type SiteBrand, siteOf } from "./sites";

/** Trang đang render (proxy.ts đã đặt header x-leadscan-site cho mọi request). Chỉ dùng trong server component. */
export async function currentSite(): Promise<SiteBrand> {
  return siteOf((await headers()).get(SITE_HEADER));
}

import type { MetadataRoute } from "next";
import { listEpisodes } from "@/lib/db";
import { episodeHref } from "@/lib/format";

export const dynamic = "force-dynamic";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  const episodes = listEpisodes().map((e) => ({
    url: `${base}${episodeHref(e.series, e.no)}`,
    changeFrequency: "weekly" as const,
    priority: 0.6,
  }));
  return [
    { url: `${base}/`, changeFrequency: "daily", priority: 1 },
    { url: `${base}/ara`, changeFrequency: "daily", priority: 0.8 },
    ...episodes,
  ];
}

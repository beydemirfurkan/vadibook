import { NextResponse, type NextRequest } from "next/server";
import { isSeries } from "@/lib/format";
import { MAX_QUERY_LEN, search } from "@/lib/search";

/**
 * Public search endpoint. Only ever returns cropped snippets (see lib/search.ts); the full
 * utterance text is not retrievable through this route.
 */
export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const q = (sp.get("q") ?? "").trim();
  if (!q || q.length > MAX_QUERY_LEN) {
    return NextResponse.json({ error: `q gerekli (1-${MAX_QUERY_LEN} karakter)` }, { status: 400 });
  }
  const seriesRaw = sp.get("series");
  if (seriesRaw !== null && !isSeries(seriesRaw)) {
    return NextResponse.json({ error: "series: kv | pusu" }, { status: 400 });
  }
  const epRaw = sp.get("ep");
  if (epRaw !== null && !/^\d{1,3}$/.test(epRaw)) {
    return NextResponse.json({ error: "ep: 1-999" }, { status: 400 });
  }
  const pageRaw = sp.get("page");
  if (pageRaw !== null && !/^\d{1,3}$/.test(pageRaw)) {
    return NextResponse.json({ error: "page: 1-999" }, { status: 400 });
  }

  const result = await search({
    q,
    series: seriesRaw ?? undefined,
    ep: epRaw !== null ? Number(epRaw) : undefined,
    page: pageRaw !== null ? Number(pageRaw) : 1,
  });

  return NextResponse.json(result, {
    headers: {
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

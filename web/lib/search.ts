import "server-only";
import { Meilisearch } from "meilisearch";
import type { Series } from "./format";

export type Hit = {
  id: string;
  series: Series;
  ep: number;
  start: number;
  end: number;
  speaker: string;
  ytUrl: string;
  /** Cropped, ≤ CROP_WORDS words, with <mark> around matches. Never the full utterance. */
  snippet: string;
};

export type SearchParams = { q: string; series?: Series; ep?: number; page?: number };
export type SearchResult = { hits: Hit[]; total: number; page: number; pages: number; ms: number };

export const HITS_PER_PAGE = 20;
export const CROP_WORDS = 25;
export const MAX_QUERY_LEN = 200;

type RawHit = {
  id: string;
  series: Series;
  ep: number;
  start: number;
  end: number;
  speaker: string;
  yt_url: string;
  _formatted?: { text?: string };
};

let client: Meilisearch | null = null;

function meili(): Meilisearch {
  if (!client) {
    const host = process.env.MEILI_HOST;
    const apiKey = process.env.MEILI_SEARCH_KEY;
    if (!host || !apiKey) throw new Error("MEILI_HOST / MEILI_SEARCH_KEY tanımlı değil");
    client = new Meilisearch({ host, apiKey });
  }
  return client;
}

export async function search({ q, series, ep, page = 1 }: SearchParams): Promise<SearchResult> {
  const filter: string[] = [];
  if (series) filter.push(`series = ${series}`);
  if (ep !== undefined) filter.push(`ep = ${ep}`);

  const res = await meili().index<RawHit>("utterances").search(q, {
    // Deliberately no `text` here: the browser only ever sees the crop below.
    attributesToRetrieve: ["id", "series", "ep", "start", "end", "speaker", "yt_url"],
    attributesToCrop: ["text"],
    cropLength: CROP_WORDS,
    attributesToHighlight: ["text"],
    highlightPreTag: "<mark>",
    highlightPostTag: "</mark>",
    filter: filter.length ? filter : undefined,
    hitsPerPage: HITS_PER_PAGE,
    page,
    sort: series && ep !== undefined ? ["start:asc"] : undefined,
  });

  return {
    hits: res.hits.map((h: RawHit) => ({
      id: h.id,
      series: h.series,
      ep: h.ep,
      start: h.start,
      end: h.end,
      speaker: h.speaker,
      ytUrl: h.yt_url,
      snippet: h._formatted?.text ?? "",
    })),
    total: res.totalHits ?? 0,
    page: res.page ?? page,
    pages: res.totalPages ?? 1,
    ms: res.processingTimeMs,
  };
}

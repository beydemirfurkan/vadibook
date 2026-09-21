export type Series = "kv" | "pusu";

export function fmtTime(sec: number): string {
  const s = Math.floor(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m);
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(r).padStart(2, "0")}`;
}

/** "p1:SPEAKER_07" → "Konuşmacı 7". Character names replace this in Faz 3. */
export function speakerLabel(raw: string): string {
  const local = raw.includes(":") ? raw.split(":", 2)[1] : raw;
  const m = /^SPEAKER_(\d+)$/.exec(local);
  return m ? `Konuşmacı ${Number(m[1])}` : "Bilinmeyen";
}

export function seriesName(series: Series): string {
  return series === "kv" ? "Kurtlar Vadisi" : "Kurtlar Vadisi Pusu";
}

export function seriesShort(series: Series): string {
  return series === "kv" ? "KV" : "Pusu";
}

export function episodeHref(series: Series, no: number): string {
  return `/bolum/${series}/${no}`;
}

const ESC: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

/** Escape everything, then re-enable only the <mark> tags Meilisearch inserted for us. */
export function renderSnippet(snippet: string): string {
  return snippet
    .replace(/[&<>"']/g, (c) => ESC[c])
    .replace(/&lt;mark&gt;/g, "<mark>")
    .replace(/&lt;\/mark&gt;/g, "</mark>");
}

export function isSeries(v: unknown): v is Series {
  return v === "kv" || v === "pusu";
}

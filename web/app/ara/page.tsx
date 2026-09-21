import type { Metadata } from "next";
import Link from "next/link";
import { ResultCard } from "@/components/ResultCard";
import { SearchBox } from "@/components/SearchBox";
import { isSeries, seriesName, type Series } from "@/lib/format";
import { HITS_PER_PAGE, MAX_QUERY_LEN, search } from "@/lib/search";

type SP = { q?: string; series?: string; ep?: string; page?: string };
type Props = { searchParams: Promise<SP> };

function parse(sp: SP) {
  const q = (sp.q ?? "").trim().slice(0, MAX_QUERY_LEN);
  const series: Series | undefined = isSeries(sp.series) ? sp.series : undefined;
  const ep = sp.ep && /^\d+$/.test(sp.ep) ? Number(sp.ep) : undefined;
  const page = sp.page && /^\d+$/.test(sp.page) ? Math.max(1, Number(sp.page)) : 1;
  return { q, series, ep, page };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { q } = parse(await searchParams);
  return { title: q ? `“${q}” için sonuçlar` : "Ara" };
}

export default async function SearchPage({ searchParams }: Props) {
  const { q, series, ep, page } = parse(await searchParams);
  const result = q ? await search({ q, series, ep, page }) : null;
  const nf = new Intl.NumberFormat("tr-TR");

  const hrefFor = (over: Partial<{ series: Series | undefined; page: number }>) => {
    const p = new URLSearchParams({ q });
    const s = "series" in over ? over.series : series;
    if (s) p.set("series", s);
    if (ep !== undefined) p.set("ep", String(ep));
    const pg = over.page ?? 1;
    if (pg > 1) p.set("page", String(pg));
    return `/ara?${p.toString()}`;
  };

  return (
    <div className="space-y-8">
      <SearchBox initialQuery={q} series={series} ep={ep} size="hero" />

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-rule pb-3">
        <ul className="flex gap-1 font-mono text-[0.7rem] uppercase tracking-[0.12em]">
          {(
            [
              [undefined, "Tümü"],
              ["kv", "Kurtlar Vadisi"],
              ["pusu", "Pusu"],
            ] as [Series | undefined, string][]
          ).map(([s, label]) => (
            <li key={label}>
              <Link
                href={hrefFor({ series: s })}
                className={`inline-block px-3 py-1 ${series === s ? "bg-ink text-paper" : "text-ink-2 hover:text-stamp"}`}
              >
                {label}
              </Link>
            </li>
          ))}
          {ep !== undefined && series && (
            <li className="px-3 py-1 text-stamp">
              {seriesName(series)} · {ep}. Bölüm{" "}
              <Link href={`/ara?q=${encodeURIComponent(q)}`} className="ml-1 text-ink-3 hover:text-stamp" aria-label="Bölüm filtresini kaldır">
                ×
              </Link>
            </li>
          )}
        </ul>
        {result && (
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-ink-3">
            {nf.format(result.total)} sonuç · {result.ms} ms
          </p>
        )}
      </div>

      {!q && <p className="font-body text-ink-2">Aramak için bir şey yaz.</p>}

      {result && result.hits.length === 0 && (
        <div className="space-y-2 py-10 text-center">
          <p className="font-display text-2xl text-ink">Sonuç yok.</p>
          <p className="font-body text-ink-2">
            Şapkasız da dene (<em>kasifoglu</em>), ya da daha kısa bir kelime. Arşiv henüz dolmaya devam ediyor.
          </p>
        </div>
      )}

      {result && result.hits.length > 0 && (
        <ol className="space-y-3">
          {result.hits.map((h, i) => (
            <li key={h.id}>
              <ResultCard hit={h} index={i} />
            </li>
          ))}
        </ol>
      )}

      {result && result.pages > 1 && (
        <nav className="flex items-center justify-between font-mono text-[0.7rem] uppercase tracking-[0.12em]" aria-label="Sayfalar">
          {page > 1 ? (
            <Link href={hrefFor({ page: page - 1 })} className="text-ink-2 hover:text-stamp">
              ← Önceki
            </Link>
          ) : (
            <span />
          )}
          <span className="text-ink-3">
            Sayfa {page} / {result.pages} · {HITS_PER_PAGE}&rsquo;lik
          </span>
          {page < result.pages ? (
            <Link href={hrefFor({ page: page + 1 })} className="text-ink-2 hover:text-stamp">
              Sonraki →
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </div>
  );
}

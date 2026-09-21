import type { Metadata } from "next";
import Link from "next/link";
import { ResultCard } from "@/components/ResultCard";
import { SearchBox } from "@/components/SearchBox";
import { isSeries, seriesName, type Series } from "@/lib/format";
import { MAX_QUERY_LEN, search } from "@/lib/search";

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
  const { q, series } = parse(await searchParams);
  const where = series ? seriesName(series) : "kurtlar vadisi ve pusu";
  return {
    title: q ? `"${q}" — ${where} bölümlerinde nerede geçiyor` : "ara",
    description: q
      ? `"${q}" ifadesinin ${where} bölümlerinde geçtiği yerler: bölüm, dakika, konuşmacı ve resmi videoya zaman damgalı link.`
      : "kurtlar vadisi ve pusu'nun bütün diyaloglarında ara.",
    robots: q ? { index: false, follow: true } : undefined,
  };
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

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <ul className="flex flex-wrap gap-1" aria-label="Seri filtresi">
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
                aria-current={series === s ? "true" : undefined}
                className={`navlink ${series === s ? "bg-steel text-bg hover:text-bg" : ""}`}
              >
                {label}
              </Link>
            </li>
          ))}
          {ep !== undefined && series && (
            <li>
              <Link
                href={`/ara?q=${encodeURIComponent(q)}`}
                className="navlink text-accent-2"
                aria-label={`${seriesName(series)} ${ep}. bölüm filtresini kaldır`}
              >
                {ep}. Bölüm ×
              </Link>
            </li>
          )}
        </ul>
        {result && (
          <p className="eyebrow" role="status">
            {nf.format(result.total)} sonuç · {result.ms} ms
          </p>
        )}
      </div>

      {!q && <p className="font-body text-lg text-fg-2">Aramak için bir şey yaz.</p>}

      {result && result.hits.length === 0 && (
        <div className="space-y-2 py-10 text-center">
          <p className="steel-text font-display text-2xl">Sonuç Yok.</p>
          <p className="font-body text-fg-2">
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
        <nav className="flex items-center justify-between gap-3" aria-label="Sayfalar">
          {page > 1 ? (
            <Link href={hrefFor({ page: page - 1 })} className="navlink" rel="prev">
              ← Önceki
            </Link>
          ) : (
            <span />
          )}
          <span className="eyebrow">
            Sayfa {page} / {result.pages}
          </span>
          {page < result.pages ? (
            <Link href={hrefFor({ page: page + 1 })} className="navlink" rel="next">
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

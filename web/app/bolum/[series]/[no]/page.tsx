import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SearchBox } from "@/components/SearchBox";
import { adjacentEpisodes, episodeStats, getEpisode, mentionCounts } from "@/lib/db";
import { episodeHref, fmtTime, isSeries, seriesName } from "@/lib/format";

type Params = Promise<{ series: string; no: string }>;

async function load(params: Params) {
  const { series, no } = await params;
  if (!isSeries(series) || !/^\d+$/.test(no)) return null;
  return getEpisode(series, Number(no));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const ep = await load(params);
  if (!ep) return { title: "bölüm bulunamadı" };
  const name = seriesName(ep.series);
  return {
    title: `${name} ${ep.no}. bölüm — kimler anılıyor, bölüm içi arama`,
    description: `${name} ${ep.no}. bölüm: bu bölümde adı geçen karakterler ve örgütler, bölümde geçen herhangi bir repliği ara, resmi youtube yüklemesinde tam o saniyeye git.`,
    alternates: { canonical: `/bolum/${ep.series}/${ep.no}` },
    openGraph: { title: `${name} ${ep.no}. bölüm · vadibook`, type: "video.episode" },
  };
}

export default async function EpisodePage({ params }: { params: Params }) {
  const ep = await load(params);
  if (!ep) notFound();

  const stats = episodeStats(ep.key);
  const mentions = mentionCounts(ep.key);
  const { prev, next } = adjacentEpisodes(ep.series, ep.no);
  const nf = new Intl.NumberFormat("tr-TR");
  const searchHref = (q: string) => `/ara?${new URLSearchParams({ q, series: ep.series, ep: String(ep.no) })}`;

  return (
    <div className="space-y-10 sm:space-y-12">
      <header className="rise space-y-3">
        <p className="eyebrow">{seriesName(ep.series)}</p>
        <h1 className="steel-text font-display text-4xl leading-tight sm:text-5xl">{ep.no}. Bölüm</h1>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-sm text-fg-2">
          <Item k="süre" v={fmtTime(ep.duration_sec)} />
          <Item k="konuşma" v={nf.format(stats.utterances)} />
          <Item k="diyalog" v={`${Math.round(stats.spokenSec / 60)} dk`} />
          {ep.parts.length > 1 && <Item k="parça" v={String(ep.parts.length)} />}
        </dl>
      </header>

      <figure className="rise" style={{ animationDelay: "80ms" }}>
        <div className="cinema-bezel">
          <div className="cinema-screen aspect-video w-full">
            <iframe
              className="h-full w-full"
              src={`https://www.youtube-nocookie.com/embed/${ep.yt_id}`}
              title={`${seriesName(ep.series)} ${ep.no}. Bölüm — resmi yükleme`}
              allow="accelerometer; encrypted-media; picture-in-picture"
              allowFullScreen
              loading="lazy"
            />
          </div>
        </div>
        <figcaption className="plaque">
          <span>{ep.no}. Bölüm · Resmi Pana Film yüklemesi</span>
        </figcaption>
      </figure>

      <section className="space-y-4 rise" style={{ animationDelay: "160ms" }} aria-labelledby="ara-baslik">
        <h2 id="ara-baslik" className="steel-text font-display text-2xl">
          Bu Bölümde Ara
        </h2>
        <SearchBox series={ep.series} ep={ep.no} placeholder="bu bölümde geçen bir kelime…" />
      </section>

      {mentions.length > 0 && (
        <section className="space-y-4 rise" style={{ animationDelay: "240ms" }} aria-labelledby="anilan-baslik">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="anilan-baslik" className="steel-text font-display text-2xl">
              Bu Bölümde Adı Geçenler
            </h2>
            <p className="eyebrow">kaç kez anıldı · tıkla, o bölümde ara</p>
          </div>
          <ul className="flex flex-wrap gap-2" aria-label="Bu bölümde adı geçen karakterler ve örgütler">
            {mentions.map((m) => (
              <li key={m.name}>
                <Link href={searchHref(m.name)} className="chip">
                  <span>{m.name}</span>
                  <span className="chip-count" aria-label={`${m.count} kez`}>
                    {m.count}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <nav className="flex items-center justify-between gap-4 border-t border-line pt-4" aria-label="Önceki ve sonraki bölüm">
        {prev ? (
          <Link href={episodeHref(prev.series, prev.no)} className="navlink">
            ← {prev.no}. Bölüm
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={episodeHref(next.series, next.no)} className="navlink">
            {next.no}. Bölüm →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </div>
  );
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-fg-3">{k}</dt>
      <dd className="text-fg tabular">{v}</dd>
    </div>
  );
}

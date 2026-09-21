import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SearchBox } from "@/components/SearchBox";
import { SpeakerTimeline } from "@/components/SpeakerTimeline";
import { adjacentEpisodes, episodeStats, getEpisode, speakerTimeline } from "@/lib/db";
import { episodeHref, fmtTime, isSeries, seriesName } from "@/lib/format";

type Params = Promise<{ series: string; no: string }>;

async function load(params: Params) {
  const { series, no } = await params;
  if (!isSeries(series) || !/^\d+$/.test(no)) return null;
  return getEpisode(series, Number(no));
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const ep = await load(params);
  if (!ep) return { title: "Bölüm bulunamadı" };
  return {
    title: `${seriesName(ep.series)} ${ep.no}. Bölüm`,
    description: `${seriesName(ep.series)} ${ep.no}. bölümün konuşmacı çizelgesi ve bölüm içi arama.`,
  };
}

export default async function EpisodePage({ params }: { params: Params }) {
  const ep = await load(params);
  if (!ep) notFound();

  const stats = episodeStats(ep.key);
  const turns = speakerTimeline(ep.key);
  const { prev, next } = adjacentEpisodes(ep.series, ep.no);
  const nf = new Intl.NumberFormat("tr-TR");

  return (
    <div className="space-y-10">
      <header className="rise space-y-4">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-ink-3">{seriesName(ep.series)}</p>
        <h1 className="font-display text-[2.4rem] leading-tight tracking-tight text-ink sm:text-5xl">{ep.no}. Bölüm</h1>
        <dl className="flex flex-wrap gap-x-8 gap-y-2 font-mono text-[0.72rem] uppercase tracking-[0.12em] text-ink-2">
          <Item k="Süre" v={fmtTime(ep.duration_sec)} />
          <Item k="Konuşma" v={nf.format(stats.utterances)} />
          <Item k="Diyalog" v={`${Math.round(stats.spokenSec / 60)} dk`} />
          <Item k="Konuşmacı" v={String(stats.speakers)} />
          {ep.parts.length > 1 && <Item k="Parça" v={String(ep.parts.length)} />}
        </dl>
      </header>

      <section className="rise" style={{ animationDelay: "80ms" }}>
        <div className="aspect-video w-full border border-rule bg-ink">
          <iframe
            className="h-full w-full"
            src={`https://www.youtube-nocookie.com/embed/${ep.yt_id}`}
            title={`${seriesName(ep.series)} ${ep.no}. Bölüm — resmi yükleme`}
            allow="accelerometer; encrypted-media; picture-in-picture"
            allowFullScreen
            loading="lazy"
          />
        </div>
        <p className="mt-2 font-mono text-[0.68rem] uppercase tracking-[0.12em] text-ink-3">
          Resmi Pana Film yüklemesi · sesi ve görüntüyü biz barındırmıyoruz
        </p>
      </section>

      <section className="space-y-4 rise" style={{ animationDelay: "160ms" }}>
        <h2 className="font-display text-2xl text-ink">Bu bölümde ara</h2>
        <SearchBox series={ep.series} ep={ep.no} placeholder="bu bölümde geçen bir kelime…" />
      </section>

      <section className="space-y-4 rise" style={{ animationDelay: "240ms" }}>
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl text-ink">Kim ne zaman konuştu</h2>
          <p className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-ink-3">
            en çok konuşan 12 · etiketler otomatik
          </p>
        </div>
        <div className="card p-4">
          <SpeakerTimeline turns={turns} duration={ep.duration_sec} />
        </div>
      </section>

      <nav className="flex items-center justify-between border-t border-rule pt-4 font-mono text-[0.7rem] uppercase tracking-[0.12em]" aria-label="Bölümler arası">
        {prev ? (
          <Link href={episodeHref(prev.series, prev.no)} className="text-ink-2 hover:text-stamp">
            ← {prev.no}. Bölüm
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={episodeHref(next.series, next.no)} className="text-ink-2 hover:text-stamp">
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
      <dt className="text-ink-3">{k}</dt>
      <dd className="text-ink tabular">{v}</dd>
    </div>
  );
}

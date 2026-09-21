import Link from "next/link";
import { SearchBox } from "@/components/SearchBox";
import { corpusStats, listEpisodes } from "@/lib/db";
import { episodeHref, seriesShort } from "@/lib/format";

// The archive fills up while the site runs: read counts per request, never at build time.
export const dynamic = "force-dynamic";

const TOTAL_EPISODES = 397;
const EXAMPLES = ["Kaşifoğlu", "İskender Büyük", "Tapınakçılar", "derin devlet", "Ömer Baba", "Çakır"];

const nf = new Intl.NumberFormat("tr-TR");

export default function Home() {
  const stats = corpusStats();
  const episodes = listEpisodes();
  const recent = [...episodes].reverse().slice(0, 12);
  const pct = Math.round((stats.episodes / TOTAL_EPISODES) * 100);

  return (
    <div className="space-y-16">
      <section className="rise space-y-8 pt-6 sm:pt-12">
        <p className="stamp">Bilirkişi aylarca inceleyecek · biz 3 saniyede</p>
        <h1 className="font-display text-[2.6rem] leading-[1.02] tracking-tight text-ink sm:text-[4.2rem]">
          397 bölüm. <em className="not-italic text-stamp">Her cümle.</em>
          <br />
          Saniyesine kadar.
        </h1>
        <p className="max-w-2xl font-body text-lg leading-relaxed text-ink-2">
          Kurtlar Vadisi ve Pusu&rsquo;nun bütün diyalogları, kim ne zaman söyledi bilgisiyle aranabilir.
          Her sonuç resmi YouTube yüklemesinde tam o saniyeye götürür.
        </p>
        <SearchBox size="hero" autoFocus placeholder="bir isim, bir örgüt, bir cümle…" />
        <ul className="flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <li key={q}>
              <Link
                href={`/ara?q=${encodeURIComponent(q)}`}
                className="inline-block border border-ink-3 px-3 py-1 font-mono text-[0.7rem] uppercase tracking-[0.12em] text-ink-2 hover:border-stamp hover:text-stamp"
              >
                {q}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <hr className="hr-double" />

      <section className="grid gap-8 sm:grid-cols-3">
        <Stat label="Bölüm işlendi" value={`${stats.episodes} / ${TOTAL_EPISODES}`} note={`%${pct} · arşiv dolmaya devam ediyor`} />
        <Stat label="Konuşma" value={nf.format(stats.utterances)} note="konuşmacı etiketli, kelime zamanlı" />
        <Stat label="Saat" value={nf.format(Math.round(stats.hours))} note={`${nf.format(Math.round(stats.spokenHours))} saati diyalog`} />
      </section>

      <section id="bolumler" className="space-y-5">
        <h2 className="font-display text-2xl text-ink">Son işlenen bölümler</h2>
        <ul className="grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {recent.map((e) => (
            <li key={e.key} className="flex items-baseline justify-between border-b border-rule py-2">
              <Link href={episodeHref(e.series, e.no)} className="font-body text-ink hover:text-stamp">
                {seriesShort(e.series)} · {e.no}. Bölüm
              </Link>
              <span className="font-mono text-[0.7rem] text-ink-3 tabular">{Math.round(e.duration_sec / 60)} dk</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="space-y-1">
      <div className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-ink-3">{label}</div>
      <div className="font-display text-4xl text-ink tabular">{value}</div>
      <div className="font-mono text-[0.7rem] text-ink-2">{note}</div>
    </div>
  );
}

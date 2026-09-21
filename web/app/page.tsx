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
    <div className="space-y-20">
      <section className="rise space-y-9 pt-10 sm:pt-20">
        <p className="badge">Bilirkişi aylarca inceleyecek · biz 3 saniyede</p>
        <h1 className="font-display text-[2.3rem] leading-[1.08] sm:text-[4.4rem]">
          <span className="steel-text">397 Bölüm.</span> <span className="steel-text-accent">Her Cümle.</span>
          <br />
          <span className="steel-text">Saniyesine Kadar.</span>
        </h1>
        <p className="max-w-2xl font-body text-xl leading-relaxed text-fg-2">
          Kurtlar Vadisi ve Pusu&rsquo;nun bütün diyalogları, kim ne zaman söyledi bilgisiyle aranabilir.
          Her sonuç resmi YouTube yüklemesinde tam o saniyeye götürür.
        </p>
        <SearchBox size="hero" autoFocus placeholder="bir isim, bir örgüt, bir cümle…" />
        <ul className="flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <li key={q}>
              <Link
                href={`/ara?q=${encodeURIComponent(q)}`}
                className="inline-block border border-line-2 px-3 py-1 font-mono text-[0.66rem] uppercase tracking-[0.14em] text-fg-2 hover:border-steel hover:text-moon"
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
        <h2 className="steel-text font-display text-2xl">Son İşlenen Bölümler</h2>
        <ul className="grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {recent.map((e) => (
            <li key={e.key} className="flex items-baseline justify-between border-b border-line py-2">
              <Link href={episodeHref(e.series, e.no)} className="font-body text-lg text-fg hover:text-moon">
                {seriesShort(e.series)} · {e.no}. Bölüm
              </Link>
              <span className="font-mono text-[0.68rem] text-fg-3 tabular">{Math.round(e.duration_sec / 60)} dk</span>
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
      <div className="font-mono text-[0.66rem] uppercase tracking-[0.16em] text-fg-3">{label}</div>
      <div className="steel-text font-display text-4xl tabular">{value}</div>
      <div className="font-mono text-[0.68rem] text-fg-2">{note}</div>
    </div>
  );
}

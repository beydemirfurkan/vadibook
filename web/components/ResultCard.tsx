import Link from "next/link";
import type { Hit } from "@/lib/search";
import { episodeHref, fmtTime, renderSnippet, seriesShort, speakerLabel } from "@/lib/format";

export function ResultCard({ hit, index }: { hit: Hit; index: number }) {
  return (
    <article
      className="card rise grid gap-3 p-4 sm:grid-cols-[9rem_1fr_auto] sm:gap-6 sm:p-5"
      style={{ animationDelay: `${Math.min(index, 12) * 50}ms` }}
    >
      <div className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-fg-2 leading-6">
        <Link href={episodeHref(hit.series, hit.ep)} className="text-steel hover:text-moon">
          {seriesShort(hit.series)} · {hit.ep}. Bölüm
        </Link>
        <div className="tabular">{fmtTime(hit.start)}</div>
        <div className="text-fg-3">{speakerLabel(hit.speaker)}</div>
      </div>

      <p
        className="font-body text-[1.2rem] leading-relaxed text-fg"
        dangerouslySetInnerHTML={{ __html: `…${renderSnippet(hit.snippet)}…` }}
      />

      <a
        href={hit.ytUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="group inline-flex items-center gap-2 self-start whitespace-nowrap font-mono text-[0.68rem] uppercase tracking-[0.16em] text-accent-2 hover:text-moon"
      >
        <span aria-hidden className="inline-block transition-transform group-hover:translate-x-0.5">▶</span>
        O anı izle
      </a>
    </article>
  );
}

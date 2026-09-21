import Link from "next/link";
import type { Hit } from "@/lib/search";
import { episodeHref, fmtTime, renderSnippet, seriesShort, speakerLabel } from "@/lib/format";

export function ResultCard({ hit, index }: { hit: Hit; index: number }) {
  return (
    <article
      className="card rise flex flex-col gap-3 p-4 sm:grid sm:grid-cols-[9.5rem_1fr_auto] sm:gap-6 sm:p-5"
      style={{ animationDelay: `${Math.min(index, 12) * 50}ms` }}
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 font-mono text-sm text-fg-2 sm:flex-col sm:gap-1">
        <Link href={episodeHref(hit.series, hit.ep)} className="text-steel underline-offset-4 hover:text-moon hover:underline">
          {seriesShort(hit.series)} · {hit.ep}. Bölüm
        </Link>
        <span className="tabular">{fmtTime(hit.start)}</span>
        <span className="text-fg-3">{speakerLabel(hit.speaker)}</span>
      </div>

      <p
        className="font-body text-[1.2rem] leading-relaxed text-fg"
        dangerouslySetInnerHTML={{ __html: `…${renderSnippet(hit.snippet)}…` }}
      />

      <a
        href={hit.ytUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="group inline-flex min-h-11 items-center gap-2 self-start whitespace-nowrap font-mono text-sm text-accent-2 hover:text-moon"
        aria-label={`${seriesShort(hit.series)} ${hit.ep}. bölüm, ${fmtTime(hit.start)} — YouTube'da o anı izle`}
      >
        <span aria-hidden className="inline-block transition-transform group-hover:translate-x-0.5">
          ▶
        </span>
        O anı izle
      </a>
    </article>
  );
}

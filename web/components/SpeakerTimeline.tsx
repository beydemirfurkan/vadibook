import type { TimelineTurn } from "@/lib/db";
import { fmtTime, speakerLabel } from "@/lib/format";

/**
 * One lane per speaker, sorted by spoken time; a bar per utterance. Carries no text — only when
 * and who — so it is safe to render for everyone.
 */
export function SpeakerTimeline({ turns, duration, maxLanes = 12 }: { turns: TimelineTurn[]; duration: number; maxLanes?: number }) {
  const spoken = new Map<string, number>();
  for (const t of turns) spoken.set(t.speaker, (spoken.get(t.speaker) ?? 0) + (t.end - t.start));
  const lanes = [...spoken.entries()].sort((a, b) => b[1] - a[1]).slice(0, maxLanes);
  const laneIndex = new Map(lanes.map(([spk], i) => [spk, i]));

  const W = 1000;
  const laneH = 18;
  const labelW = 130;
  const H = lanes.length * laneH + 22;
  const x = (sec: number) => labelW + (Math.max(0, Math.min(sec, duration)) / duration) * (W - labelW - 8);
  const ticks = Array.from({ length: Math.floor(duration / 600) + 1 }, (_, i) => i * 600);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Konuşmacı zaman çizelgesi">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={0} y2={H - 20} stroke="var(--rule)" strokeWidth={1} />
          <text x={x(t)} y={H - 6} fontSize={10} fill="var(--ink-3)" fontFamily="var(--font-mono)" textAnchor="middle">
            {fmtTime(t)}
          </text>
        </g>
      ))}
      {lanes.map(([spk, sec], i) => (
        <g key={spk}>
          <text x={0} y={i * laneH + 13} fontSize={10.5} fill="var(--ink-2)" fontFamily="var(--font-mono)">
            {speakerLabel(spk)}
          </text>
          <text x={labelW - 8} y={i * laneH + 13} fontSize={9} fill="var(--ink-3)" fontFamily="var(--font-mono)" textAnchor="end">
            {Math.round(sec / 60)}dk
          </text>
        </g>
      ))}
      {turns.map((t, i) => {
        const lane = laneIndex.get(t.speaker);
        if (lane === undefined) return null;
        return (
          <rect
            key={i}
            x={x(t.start)}
            y={lane * laneH + 3}
            width={Math.max(1.2, x(t.end) - x(t.start))}
            height={laneH - 6}
            fill={lane === 0 ? "var(--stamp)" : "var(--ink)"}
            opacity={lane === 0 ? 0.85 : 0.55 - Math.min(lane, 8) * 0.03}
          >
            <title>{`${speakerLabel(t.speaker)} · ${fmtTime(t.start)}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

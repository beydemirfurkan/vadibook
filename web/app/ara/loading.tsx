export default function Loading() {
  return (
    <div className="space-y-8" aria-busy>
      <div className="skeleton h-12 w-full" />
      <div className="flex justify-between border-b border-line pb-3">
        <div className="skeleton h-5 w-56" />
        <div className="skeleton h-5 w-28" />
      </div>
      <ol className="space-y-3">
        {Array.from({ length: 6 }, (_, i) => (
          <li key={i} className="card grid gap-3 p-5 sm:grid-cols-[9rem_1fr_auto] sm:gap-6">
            <div className="space-y-2">
              <div className="skeleton h-3 w-24" />
              <div className="skeleton h-3 w-14" />
              <div className="skeleton h-3 w-20" />
            </div>
            <div className="space-y-2">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-3/4" />
            </div>
            <div className="skeleton h-3 w-20" />
          </li>
        ))}
      </ol>
      <p className="text-center font-mono text-[0.66rem] uppercase tracking-[0.18em] text-fg-3">Sis dağılıyor…</p>
    </div>
  );
}

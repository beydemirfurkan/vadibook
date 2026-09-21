"use client";

import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import type { Series } from "@/lib/format";

type Props = {
  initialQuery?: string;
  series?: Series;
  ep?: number;
  size?: "hero" | "compact";
  placeholder?: string;
  autoFocus?: boolean;
};

export function SearchBox({ initialQuery = "", series, ep, size = "compact", placeholder, autoFocus }: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);
  const id = useId();

  function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = q.trim();
    if (!trimmed) return;
    const params = new URLSearchParams({ q: trimmed });
    if (series) params.set("series", series);
    if (ep !== undefined) params.set("ep", String(ep));
    router.push(`/ara?${params.toString()}`);
  }

  const hero = size === "hero";

  return (
    <form onSubmit={submit} role="search" className="w-full">
      <label htmlFor={id} className="sr-only">
        Diyaloglarda ara
      </label>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <input
          id={id}
          name="q"
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus={autoFocus}
          autoComplete="off"
          enterKeyHint="search"
          maxLength={200}
          placeholder={placeholder ?? "bir isim, bir cümle, bir örgüt…"}
          className={`rule-input w-full font-body ${hero ? "text-2xl sm:text-4xl py-2" : "text-xl py-2"}`}
        />
        <button
          type="submit"
          className={`btn-accent min-h-11 shrink-0 font-display uppercase tracking-[0.2em] ${
            hero ? "text-sm px-7 py-3" : "text-xs px-5 py-2.5"
          }`}
        >
          Ara
        </button>
      </div>
    </form>
  );
}

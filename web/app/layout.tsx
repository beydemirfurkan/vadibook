import type { Metadata } from "next";
import Link from "next/link";
import { Fraunces, IBM_Plex_Mono, Literata } from "next/font/google";
import { Disclaimer } from "@/components/Disclaimer";
import "./globals.css";

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin", "latin-ext"],
  axes: ["opsz", "SOFT", "WONK"],
  style: ["normal", "italic"],
});

const literata = Literata({
  variable: "--font-literata",
  subsets: ["latin", "latin-ext"],
  style: ["normal", "italic"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: { default: "vadibook — Kurtlar Vadisi arşivi", template: "%s · vadibook" },
  description:
    "Kurtlar Vadisi'nin 397 bölümündeki her konuşmayı arayın, resmi YouTube yüklemesinde tam o saniyeye gidin.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="tr" className={`${fraunces.variable} ${literata.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <header className="border-b border-rule">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-6 px-4 py-4 sm:px-6">
            <Link href="/" className="flex items-baseline gap-3">
              <span className="font-display italic text-2xl tracking-tight text-ink">vadibook</span>
              <span className="stamp hidden sm:inline-block">Dosya No. 397</span>
            </Link>
            <nav className="flex items-center gap-5 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-ink-2">
              <Link href="/ara" className="hover:text-stamp">
                Ara
              </Link>
              <Link href="/#bolumler" className="hover:text-stamp">
                Bölümler
              </Link>
              {process.env.NEXT_PUBLIC_REPO_URL && (
                <a href={process.env.NEXT_PUBLIC_REPO_URL} className="hover:text-stamp" rel="noopener noreferrer">
                  GitHub
                </a>
              )}
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6">{children}</main>

        <footer className="border-t border-rule">
          <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 space-y-3">
            <Disclaimer />
            <p className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-ink-3">
              Açık kaynak · transkriptler yerel Whisper ile üretilir · konuşmacı etiketleri otomatiktir ve
              hata içerebilir
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

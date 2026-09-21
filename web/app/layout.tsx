import type { Metadata } from "next";
import Link from "next/link";
import { Cinzel, Cormorant_Garamond, IBM_Plex_Mono } from "next/font/google";
import { Disclaimer } from "@/components/Disclaimer";
import { NightSky } from "@/components/NightSky";
import "./globals.css";

const cinzel = Cinzel({
  variable: "--font-cinzel",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500"],
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  title: {
    default: "vadibook — kurtlar vadisi ve pusu'nun bütün diyalogları, aranabilir",
    template: "%s · vadibook",
  },
  description:
    "kurtlar vadisi ve kurtlar vadisi pusu'nun 397 bölümündeki her repliği ara; kim, hangi bölümde, kaçıncı dakikada demiş gör, resmi youtube yüklemesinde tam o saniyeye git.",
  metadataBase: new URL(SITE_URL),
  alternates: { canonical: "/" },
  openGraph: { type: "website", locale: "tr_TR", siteName: "vadibook", url: SITE_URL },
  twitter: { card: "summary_large_image" },
  robots: { index: true, follow: true },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "vadibook",
  url: SITE_URL,
  inLanguage: "tr",
  description: "kurtlar vadisi ve pusu'nun bütün bölümlerinin aranabilir diyalog arşivi",
  potentialAction: {
    "@type": "SearchAction",
    target: { "@type": "EntryPoint", urlTemplate: `${SITE_URL}/ara?q={search_term_string}` },
    "query-input": "required name=search_term_string",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="tr" className={`${cinzel.variable} ${cormorant.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <NightSky />

        <header className="border-b border-line bg-bg/40 backdrop-blur-sm">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-6 px-4 py-4 sm:px-6">
            <Link href="/" className="flex items-center gap-4">
              <span className="steel-text font-display text-2xl font-semibold tracking-[0.08em]">VADİBOOK</span>
              <span className="badge hidden sm:inline-block">Dosya No. 397</span>
            </Link>
            <nav className="flex items-center gap-6 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-fg-2">
              <Link href="/ara" className="hover:text-moon">
                Ara
              </Link>
              <Link href="/#bolumler" className="hover:text-moon">
                Bölümler
              </Link>
              {process.env.NEXT_PUBLIC_REPO_URL && (
                <a href={process.env.NEXT_PUBLIC_REPO_URL} className="hover:text-moon" rel="noopener noreferrer">
                  GitHub
                </a>
              )}
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6">{children}</main>

        <footer className="border-t border-line bg-bg/60 backdrop-blur-sm">
          <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 space-y-3">
            <Disclaimer />
            <p className="font-mono text-[0.66rem] uppercase tracking-[0.14em] text-fg-3">
              Açık kaynak · transkriptler yerel Whisper ile üretilir · konuşmacı etiketleri otomatiktir ve
              hata içerebilir
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Cinzel, Cormorant_Garamond, IBM_Plex_Mono } from "next/font/google";
import { Disclaimer } from "@/components/Disclaimer";
import { NightSky } from "@/components/NightSky";
import "./globals.css";

const cinzel = Cinzel({
  variable: "--font-cinzel",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500"],
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const viewport: Viewport = {
  themeColor: "#05070d",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

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
        <a href="#icerik" className="skip-link">
          İçeriğe atla
        </a>
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <NightSky />

        <header className="border-b border-line bg-bg/40 backdrop-blur-sm">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-4 py-2 sm:px-6">
            <Link href="/" className="flex min-h-11 items-center gap-4" aria-label="vadibook ana sayfa">
              <span className="steel-text font-display text-xl font-semibold tracking-[0.08em] sm:text-2xl">VADİBOOK</span>
              <span className="badge hidden sm:inline-block" aria-hidden>
                Dosya No. 397
              </span>
            </Link>
            <nav aria-label="Site" className="flex items-center gap-1 sm:gap-3">
              <Link href="/ara" className="navlink">
                Ara
              </Link>
              <Link href="/#bolumler" className="navlink">
                Bölümler
              </Link>
              {process.env.NEXT_PUBLIC_REPO_URL && (
                <a href={process.env.NEXT_PUBLIC_REPO_URL} className="navlink" rel="noopener noreferrer">
                  GitHub
                </a>
              )}
            </nav>
          </div>
        </header>

        <main id="icerik" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>

        <footer className="border-t border-line bg-bg/60 backdrop-blur-sm">
          <div className="mx-auto w-full max-w-5xl space-y-3 px-4 py-6 sm:px-6">
            <Disclaimer />
            <p className="font-mono text-xs leading-relaxed text-fg-3">
              açık kaynak · transkriptler yerel whisper ile üretilir · konuşmacı etiketleri otomatiktir ve hata
              içerebilir
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

import { ImageResponse } from "next/og";

export const alt = "vadibook — Kurtlar Vadisi'nin 397 bölümü, her cümle, saniyesine kadar";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** Cinzel (OFL) straight from Google Fonts; the card still renders with the default font if this fails. */
async function loadCinzel(): Promise<ArrayBuffer | null> {
  try {
    const css = await (
      await fetch("https://fonts.googleapis.com/css2?family=Cinzel:wght@600", {
        headers: { "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0" },
      })
    ).text();
    // Satori accepts TTF, OTF and WOFF (not WOFF2); this UA makes Google serve WOFF.
    const url = css.match(/src: url\((.+?)\) format\('(?:truetype|opentype|woff)'\)/)?.[1];
    if (!url) return null;
    return await (await fetch(url)).arrayBuffer();
  } catch {
    return null;
  }
}

export default async function Image() {
  const cinzel = await loadCinzel();
  const display = cinzel ? "Cinzel" : "serif";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          position: "relative",
          background: "linear-gradient(180deg, #03050a 0%, #070c18 40%, #0b1224 100%)",
          fontFamily: display,
          color: "#e6ebf4",
        }}
      >
        {/* moon */}
        <div
          style={{
            position: "absolute",
            top: 70,
            right: 120,
            width: 150,
            height: 150,
            borderRadius: 999,
            background: "radial-gradient(circle at 38% 36%, #ffffff 0%, #f3f6ff 34%, #dde4f4 68%, #c3cce2 100%)",
            boxShadow: "0 0 60px 18px rgba(225,234,255,0.5), 0 0 200px 80px rgba(160,180,230,0.22)",
          }}
        />
        {/* mist band */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 230,
            height: 260,
            background: "linear-gradient(180deg, rgba(150,168,205,0) 0%, rgba(150,168,205,0.22) 45%, rgba(150,168,205,0) 100%)",
          }}
        />
        {/* ridges */}
        <svg
          width="1200"
          height="240"
          viewBox="0 0 1440 320"
          preserveAspectRatio="none"
          style={{ position: "absolute", left: 0, bottom: 0 }}
        >
          <path
            fill="#182238"
            d="M0 230 L80 200 L150 215 L230 160 L300 190 L370 150 L430 175 L520 120 L600 165 L680 140 L760 175 L840 130 L920 170 L1000 145 L1080 185 L1160 150 L1240 190 L1320 165 L1440 200 L1440 320 L0 320 Z"
          />
          <path
            fill="#070b16"
            d="M0 290 L60 270 L130 285 L210 240 L290 275 L360 250 L450 280 L530 235 L610 270 L700 250 L790 285 L880 245 L960 275 L1050 255 L1140 290 L1230 260 L1320 285 L1440 265 L1440 320 L0 320 Z"
          />
        </svg>

        <div style={{ display: "flex", flexDirection: "column", padding: "0 80px 84px", position: "relative" }}>
          <div
            style={{
              display: "flex",
              fontSize: 22,
              letterSpacing: 8,
              color: "#c7d0dd",
              textTransform: "uppercase",
              marginBottom: 18,
            }}
          >
            VADİBOOK · DOSYA NO. 397
          </div>
          <div style={{ display: "flex", fontSize: 76, lineHeight: 1.05, letterSpacing: 3, color: "#eef2f8" }}>
            397 BÖLÜM. <span style={{ color: "#e2323b", marginLeft: 22 }}>HER CÜMLE.</span>
          </div>
          <div style={{ display: "flex", fontSize: 76, lineHeight: 1.05, letterSpacing: 3, color: "#eef2f8" }}>
            SANİYESİNE KADAR.
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 26,
              fontSize: 24,
              color: "#a9b3c6",
              fontFamily: "serif",
            }}
          >
            Kurtlar Vadisi&rsquo;nin bütün diyalogları — kim, ne zaman, hangi saniyede.
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: cinzel ? [{ name: "Cinzel", data: cinzel, style: "normal", weight: 600 }] : undefined,
    },
  );
}

/**
 * Fixed, non-interactive backdrop: star field, two rolling cloud decks (one lit by the moon),
 * the moon riding above them with two soft light shafts, an original mountain silhouette with a
 * lone wolf on the far ridge, and a counter-drifting ground fog.
 * Pure CSS + inline SVG; the cloud textures are fractal-noise SVGs rasterised once.
 */
export function NightSky() {
  return (
    <div className="sky" aria-hidden>
      <div className="stars stars-3" />
      <div className="stars stars-2" />
      <div className="stars stars-1" />
      <div className="deck deck-high" />
      <div className="deck deck-mid" />
      <div className="deck deck-lit" />
      <div className="shaft shaft-1" />
      <div className="shaft shaft-2" />
      <div className="moon" />
      <svg className="mountains" viewBox="0 0 1440 320" preserveAspectRatio="none">
        <defs>
          <linearGradient id="ridge-far" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#1a2440" />
            <stop offset="1" stopColor="#0b1224" />
          </linearGradient>
          <linearGradient id="ridge-near" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#0c1324" />
            <stop offset="1" stopColor="#04060c" />
          </linearGradient>
        </defs>
        <path
          fill="url(#ridge-far)"
          d="M0 230 L80 200 L150 215 L230 160 L300 190 L370 150 L430 175 L520 120 L600 165 L680 140 L760 175 L840 130 L920 170 L1000 145 L1080 185 L1160 150 L1240 190 L1320 165 L1440 200 L1440 320 L0 320 Z"
        />
        <path
          fill="url(#ridge-near)"
          d="M0 290 L60 270 L130 285 L210 240 L290 275 L360 250 L450 280 L530 235 L610 270 L700 250 L790 285 L880 245 L960 275 L1050 255 L1140 290 L1230 260 L1320 285 L1440 265 L1440 320 L0 320 Z"
        />
      </svg>
      {/* lone wolf howling at the moon, standing on the far-ridge peak at (1160,150) */}
      <svg className="wolf" viewBox="0 0 100 56" preserveAspectRatio="xMidYMax meet">
        <path
          fill="#070a14"
          d="M4 40 L10 28 L16 24 L30 22 L44 21 L54 16 L58 8 L60 3 L63 6 L66 1 L69 7 L74 6 L88 1 L90 4 L86 8 L76 12 L70 16 L66 22 L60 27 L58 34 L57 46 L61 48 L52 48 L50 40 L46 36 L40 37 L36 44 L38 49 L30 49 L28 42 L24 40 L20 44 L18 50 L10 50 L12 44 L8 46 L4 44 Z"
        />
      </svg>
      <div className="fog" />
      <div className="haze" />
    </div>
  );
}

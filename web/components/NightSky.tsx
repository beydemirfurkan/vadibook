/**
 * Fixed, non-interactive backdrop: star field, moon, drifting clouds and a mountain silhouette.
 * Pure CSS + one inline SVG, no image assets.
 */
export function NightSky() {
  return (
    <div className="sky" aria-hidden>
      <div className="stars stars-3" />
      <div className="stars stars-2" />
      <div className="stars stars-1" />
      <div className="moon" />
      <div className="cloud cloud-1" />
      <div className="cloud cloud-2" />
      <div className="cloud cloud-3" />
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
      <div className="haze" />
    </div>
  );
}

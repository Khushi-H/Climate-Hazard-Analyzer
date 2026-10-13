import { div } from '../lib/colors'

// "Warming stripes": one stripe per year, coloured by that year's mean daily high
// relative to the average of the whole period (blue = cooler, red = hotter).
export default function Stripes({ yearly, animateKey }) {
  const vals = yearly.map((r) => r.mean_tmax)
  const finite = vals.filter((v) => v != null)
  const mean = finite.length ? finite.reduce((a, b) => a + b, 0) / finite.length : 0
  const maxAbs = Math.max(0.15, ...finite.map((v) => Math.abs(v - mean)))
  const n = yearly.length || 1
  return (
    <svg
      key={animateKey}
      className="stripes"
      viewBox={`0 0 ${n} 1`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Warming stripes: mean daily high temperature for each year from ${yearly[0]?.year} to ${yearly[yearly.length - 1]?.year}, blue cooler and red hotter than the period average.`}
    >
      {yearly.map((r, i) => {
        const anomaly = r.mean_tmax == null ? null : r.mean_tmax - mean
        return (
          <rect
            key={r.year}
            x={i}
            y={0}
            width={1.03}
            height={1}
            fill={anomaly == null ? '#dde7f0' : div(0.5 + 0.5 * (anomaly / maxAbs))}
            style={{ '--i': i }}
          >
            <title>
              {anomaly == null
                ? `${r.year}: no data`
                : `${r.year}: mean daily high ${r.mean_tmax.toFixed(1)} °C (${anomaly >= 0 ? '+' : '−'}${Math.abs(anomaly).toFixed(1)} vs period average)`}
            </title>
          </rect>
        )
      })}
    </svg>
  )
}

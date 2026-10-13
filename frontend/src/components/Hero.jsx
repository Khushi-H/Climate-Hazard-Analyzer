import { signed } from "../lib/format";
import { stripeGradient } from "../lib/colors";
import HeatRings from "./HeatRings";

const VERDICT = {
  significant_increase: {
    label: "Statistically significant increase",
    tone: "up",
  },
  significant_decrease: {
    label: "Statistically significant decrease",
    tone: "down",
  },
  not_significant: { label: "Not statistically significant", tone: "flat" },
  insufficient_data: { label: "Not enough data", tone: "flat" },
};

export default function Hero({ analysis }) {
  const h = analysis.insights.headline;
  const v = VERDICT[h.verdict] || VERDICT.insufficient_data;
  const big =
    h.pct != null
      ? `${h.pct > 0 ? "+" : h.pct < 0 ? "−" : ""}${Math.abs(Math.round(h.pct))}%`
      : h.abs_change != null
        ? signed(h.abs_change, 1)
        : "–";
  const events = analysis.events;
  const longest = events.length
    ? Math.max(...events.map((e) => e.duration))
    : 0;
  const th = analysis.threshold;
  return (
    <section className="hero shell" aria-labelledby="hero-text">
      <div className="hero-figure" data-tone={v.tone}>
        <span
          className="hero-number"
          style={{ "--stripes": stripeGradient(analysis.yearly) }}
        >
          {big}
        </span>
        <span className="hero-unit">
          heatwave days per year, first vs last {h.window_years || 10} years
        </span>
        <span className="hero-key">
          The stripes inside the number are the years, blue cooler to red
          hotter.
        </span>
      </div>
      <div className="hero-copy">
        <span className={`verdict verdict-${v.tone}`}>{v.label}</span>
        <p id="hero-text" className="hero-text">
          {h.text}
        </p>
        <dl className="facts">
          <div>
            <dt>Hot-day threshold</dt>
            <dd>
              {th.method === "fixed"
                ? `${th.value.toFixed(1)} °C`
                : `${th.min.toFixed(0)}–${th.max.toFixed(0)} °C`}
            </dd>
          </div>
          <div>
            <dt>Events found</dt>
            <dd>{events.length}</dd>
          </div>
          <div>
            <dt>Longest event</dt>
            <dd>{longest} days</dd>
          </div>
        </dl>
      </div>
      <HeatRings
        className="hero-rings"
        events={events}
        yearly={analysis.yearly}
        startYear={analysis.params.start_year}
        endYear={analysis.params.end_year}
      />
    </section>
  );
}

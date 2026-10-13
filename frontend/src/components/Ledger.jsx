import { num, signed, pValue } from "../lib/format";

// The trend statistics behind the headline, for whichever measure is selected.
export default function Ledger({ analysis, metric }) {
  const m = analysis.trends.metrics[metric];
  if (!m.available) return null;
  const { linear: lin, mann_kendall: mk, change: ch } = m;
  const unit = m.unit;
  const rows = [
    [
      "Trend (Sen’s slope)",
      `${signed(mk.sen_slope_per_decade, 2)} ${unit} per decade`,
      "Median of all year-to-year slopes. Resistant to outlier years.",
    ],
    [
      "Trend (linear regression)",
      `${signed(lin.slope_per_decade, 2)} ${unit} per decade`,
      `R² ${num(lin.r2, 2)}, p ${pValue(lin.p_value)}`,
    ],
    [
      "Mann-Kendall trend test",
      mk.trend,
      `z ${num(mk.z, 2)}, p ${pValue(mk.p_value)}, Kendall τ ${num(mk.tau, 2)}`,
    ],
    [
      `First ${ch.window_years} years to last ${ch.window_years}`,
      `${num(ch.first_mean, 2)} to ${num(ch.last_mean, 2)}`,
      ch.pct_change == null
        ? "Percentage not defined (zero start)"
        : `${signed(ch.pct_change, 0)}% change`,
    ],
    [
      "Years used",
      `${m.n_years} of ${analysis.trends.years.length}`,
      analysis.excluded_years.length
        ? `Excluded for poor coverage: ${analysis.excluded_years.join(", ")}`
        : "Every year had at least 80% valid days",
    ],
  ];
  return (
    <section className="panel" aria-labelledby="led-h">
      <div className="panel-head">
        <h2 id="led-h">The statistics behind it</h2>
        <p className="sub">For {m.label.toLowerCase()}.</p>
      </div>
      <dl className="ledger">
        {rows.map(([k, v, note]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>
              <b>{v}</b>
              <span>{note}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

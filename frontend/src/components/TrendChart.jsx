import { useMemo, useState } from "react";
import {
  Chart as ChartJS,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from "chart.js";
import { Chart } from "react-chartjs-2";
import { seq, INK, SLATE, LINE } from "../lib/colors";
import { num } from "../lib/format";

ChartJS.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
);
ChartJS.defaults.font.family = "'Public Sans', system-ui, sans-serif";
ChartJS.defaults.color = SLATE;

export const METRIC_TABS = [
  ["heatwave_days", "Heatwave days"],
  ["events", "Events"],
  ["max_duration", "Longest event"],
  ["mean_intensity", "Intensity"],
];

export default function TrendChart({ analysis, metric, setMetric }) {
  const [asTable, setAsTable] = useState(false);
  const t = analysis.trends;
  const m = t.metrics[metric];
  const years = t.years;

  const data = useMemo(() => {
    if (!m.available) return null;
    const vals = m.series.filter((v) => v != null);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const norm = (v) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
    return {
      labels: years,
      datasets: [
        {
          type: "bar",
          label: m.label,
          data: m.series,
          backgroundColor: m.series.map((v) =>
            v == null ? "transparent" : seq(0.12 + 0.88 * norm(v)),
          ),
          borderRadius: { topLeft: 4, topRight: 4 },
          borderSkipped: "bottom",
          maxBarThickness: 22,
          order: 3,
        },
        {
          type: "line",
          label: `${t.rolling_window}-year rolling mean`,
          data: m.rolling,
          borderColor: INK,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.3,
          order: 1,
        },
        {
          type: "line",
          label: "Linear fit",
          data: m.fit,
          borderColor: SLATE,
          borderDash: [6, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 0,
          order: 2,
        },
      ],
    };
  }, [m, years, t.rolling_window]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: INK,
        padding: 10,
        cornerRadius: 8,
        titleFont: { weight: "600" },
        callbacks: {
          label: (c) =>
            c.raw == null
              ? null
              : `${c.dataset.label}: ${num(c.raw, 2)} ${c.datasetIndex === 0 ? m.unit : ""}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        border: { color: LINE },
        ticks: { maxTicksLimit: 14, maxRotation: 0 },
      },
      y: {
        beginAtZero: true,
        min: 0,
        grid: { color: "rgba(12,26,51,0.07)" },
        border: { display: false },
        title: { display: true, text: m.unit },
        ticks: { precision: 0 },
      },
    },
  };

  return (
    <section className="panel chart-panel" aria-labelledby="trend-h">
      <div className="panel-head">
        <h2 id="trend-h">Trend over time</h2>
        <div className="tabs" role="tablist" aria-label="Measure">
          {METRIC_TABS.map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={metric === id}
              className={metric === id ? "on" : ""}
              onClick={() => setMetric(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {m.available ? (
        <>
          <ul className="legend" aria-label="Chart legend">
            <li>
              <i className="sw sw-bar" />
              {m.label} each year (darker is higher)
            </li>
            <li>
              <i className="sw sw-line" />
              {t.rolling_window}-year rolling mean
            </li>
            <li>
              <i className="sw sw-dash" />
              Linear fit, {num(m.linear.slope_per_decade, 2)} per decade
            </li>
          </ul>
          {asTable ? (
            <div className="table-wrap" tabIndex={0}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Year</th>
                    <th>
                      {m.label} ({m.unit})
                    </th>
                    <th>Rolling mean</th>
                    <th>Linear fit</th>
                  </tr>
                </thead>
                <tbody>
                  {years.map((y, i) => (
                    <tr key={y}>
                      <td>{y}</td>
                      <td>
                        {m.series[i] == null ? "excluded" : num(m.series[i], 2)}
                      </td>
                      <td>{num(m.rolling[i], 2)}</td>
                      <td>{num(m.fit[i], 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="chart-box">
              <Chart
                type="bar"
                data={data}
                options={options}
                aria-label={`${m.label} per year with rolling mean and linear fit`}
                role="img"
              />
            </div>
          )}
        </>
      ) : (
        <p className="empty">
          {m.reason || "This measure is not available for the selected data."}
        </p>
      )}

      <div className="panel-foot">
        <button className="link" onClick={() => setAsTable((v) => !v)}>
          {asTable ? "Show chart" : "Show as table"}
        </button>
      </div>
    </section>
  );
}

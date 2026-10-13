import { num, signed, pValue, ordinal } from "../lib/format";
import "./robustness.css";

const TONE = {
  up: "significant increase",
  down: "significant decrease",
  flat: "no clear trend",
  na: "not enough years",
};

function toneOf(c) {
  if (!c || !c.available) return "na";
  if (c.trend === "increasing") return "up";
  if (c.trend === "decreasing") return "down";
  return "flat";
}

// The headline trend re-tested with stricter and looser definitions of a heatwave.
// Every cell is a full re-analysis of the same record: a different percentile and a different minimum length.
export default function Robustness({ robustness }) {
  if (!robustness || !robustness.cells || !robustness.cells.length) return null;
  const { cells, percentiles, min_days: lengths, summary } = robustness;
  const find = (p, d) =>
    cells.find((c) => c.percentile === p && c.min_days === d);
  const anyFew = cells.some((c) => c.few_events);

  return (
    <section className="panel robust" aria-labelledby="rob-h">
      <div className="panel-head">
        <h2 id="rob-h">Does the definition change the answer?</h2>
        <p className="sub">
          The same record, re-analysed with stricter and looser definitions of a
          heatwave. Each cell is the trend in heatwave days per year.
        </p>
      </div>

      <p
        className="rob-verdict"
        data-verdict={summary.verdict}
        data-dominant={summary.dominant || ""}
      >
        {summary.text}
      </p>

      <div
        className="rob-scroll"
        tabIndex={0}
        role="region"
        aria-label="Trend for each definition of a heatwave"
      >
        <table className="rob-grid">
          <caption className="sr-only">
            Change in heatwave days per decade for each combination of hot-day
            percentile and minimum length.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="rob-corner">
                A hot day is above the
              </th>
              {lengths.map((d) => (
                <th scope="col" key={d}>
                  {d}+ days in a row
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {percentiles.map((p) => (
              <tr key={p}>
                <th scope="row">{ordinal(p)} percentile</th>
                {lengths.map((d) => {
                  const c = find(p, d);
                  const tone = toneOf(c);
                  return (
                    <td key={d}>
                      <div
                        className={`rob-cell tone-${tone}${c && c.current ? " is-current" : ""}`}
                        title={
                          c && c.available
                            ? `${TONE[tone]}: ${signed(c.sen_per_decade, 2)} days per decade, p ${pValue(c.p_value)}, ${c.events} events, threshold ${num(c.threshold, 1)} °C`
                            : "Not enough usable years for a trend"
                        }
                      >
                        {c && c.current && (
                          <span className="rob-you">your setting</span>
                        )}
                        {c && c.available ? (
                          <>
                            <b>{signed(c.sen_per_decade, 1)}</b>
                            <span className="rob-what">{TONE[tone]}</span>
                            <span className="rob-n">
                              {c.events} events{c.few_events ? " *" : ""}
                            </span>
                          </>
                        ) : (
                          <span className="rob-what">{TONE.na}</span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="rob-key" aria-label="Colour key">
        <li>
          <i className="k-up" />
          Significant increase
        </li>
        <li>
          <i className="k-flat" />
          No clear trend
        </li>
        <li>
          <i className="k-down" />
          Significant decrease
        </li>
      </ul>
      <p className="note">
        Numbers are Sen&rsquo;s slope in days per decade;
        &ldquo;significant&rdquo; means the Mann-Kendall test gives p &lt; 0.05.
        {anyFew
          ? " An asterisk means fewer than 10 events, so that estimate is fragile."
          : ""}
      </p>
    </section>
  );
}

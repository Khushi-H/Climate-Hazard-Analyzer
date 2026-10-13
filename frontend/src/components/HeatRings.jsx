import { useMemo, useState } from "react";
import { heatDark } from "../lib/colors";

// "Heat rings": the record read like tree rings. One ring per year (the first year in the middle,
// the latest on the outside), January at the top, and a glowing arc for every heatwave. The ring
// pattern shows at a glance which part of the year heatwaves belong to and whether they are growing.
const C = 300;
const R_IN = 96;
const R_OUT = 250;
const LABEL_R = 274;
const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const MONTH_START_DOY = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
const DAYS = 366;

const doyOf = (iso) => {
  const d = new Date(iso + "T00:00:00Z");
  return Math.floor(
    (Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) -
      Date.UTC(d.getUTCFullYear(), 0, 0)) /
      864e5,
  );
};
const angle = (day) => ((day - 1) / DAYS) * 2 * Math.PI - Math.PI / 2;
const point = (r, a) => [C + r * Math.cos(a), C + r * Math.sin(a)];

function arcPath(r, fromDay, toDayExclusive) {
  const a0 = angle(fromDay);
  const a1 = angle(toDayExclusive);
  const [x0, y0] = point(r, a0);
  const [x1, y1] = point(r, a1);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r.toFixed(2)} ${r.toFixed(2)} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

export default function HeatRings({
  events,
  yearly,
  startYear,
  endYear,
  className = "",
}) {
  const [active, setActive] = useState(null);
  const years = useMemo(
    () =>
      Array.from({ length: endYear - startYear + 1 }, (_, i) => startYear + i),
    [startYear, endYear],
  );
  const n = years.length;
  const pitch = (R_OUT - R_IN) / n;
  const stroke = Math.max(2, pitch * 0.78);

  const { segs, lo, hi } = useMemo(() => {
    const out = new Map();
    let lo = Infinity;
    let hi = -Infinity;
    const add = (year, from, to, e) => {
      if (year < startYear || year > endYear || to <= from) return;
      if (!out.has(year)) out.set(year, []);
      out.get(year).push({ from, to, e });
    };
    for (const e of events) {
      lo = Math.min(lo, e.intensity);
      hi = Math.max(hi, e.intensity);
      const sy = Number(e.start.slice(0, 4));
      const ey = Number(e.end.slice(0, 4));
      if (sy === ey) add(sy, doyOf(e.start), doyOf(e.end) + 1, e);
      else {
        add(sy, doyOf(e.start), DAYS + 1, e);
        add(ey, 1, doyOf(e.end) + 1, e);
      }
    }
    return { segs: out, lo, hi };
  }, [events, startYear, endYear]);

  const byYear = useMemo(
    () => new Map(yearly.map((r) => [r.year, r])),
    [yearly],
  );
  const row = active != null ? byYear.get(active) : null;
  const colour = (e) =>
    heatDark(hi > lo ? (e.intensity - lo) / (hi - lo) : 0.5);
  const mid = (i) => R_IN + (i + 0.5) * pitch;

  const onLeave = (ev) => {
    if (ev.pointerType === "mouse") setActive(null);
  };

  return (
    <figure className={`rings ${className}`} data-active={active ?? undefined}>
      <svg
        viewBox="0 0 600 600"
        role="img"
        aria-label={`Heat rings: ${events.length} heatwaves from ${startYear} to ${endYear}. Each ring is one year, January at the top. The events table and calendar below list the same data.`}
        onPointerLeave={onLeave}
      >
        {MONTH_START_DOY.map((d, i) => {
          const a = angle(d);
          const [x0, y0] = point(R_IN - 6, a);
          const [x1, y1] = point(R_OUT + 8, a);
          const [lx, ly] = point(LABEL_R, angle(d + 14));
          return (
            <g key={MONTHS[i]}>
              <line className="tick" x1={x0} y1={y0} x2={x1} y2={y1} />
              <text
                className="month"
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {MONTHS[i]}
              </text>
            </g>
          );
        })}

        {years.map((y, i) => (
          <g
            key={y}
            className={`ring${active === y ? " on" : ""}`}
            style={{ "--i": i }}
          >
            <circle
              className="track"
              cx={C}
              cy={C}
              r={mid(i)}
              strokeWidth={stroke}
            />
            {(segs.get(y) || []).map((s, k) => (
              <path
                key={k}
                className="arc"
                d={arcPath(mid(i), s.from, s.to)}
                stroke={colour(s.e)}
                strokeWidth={stroke}
              />
            ))}
          </g>
        ))}

        <text
          className="yr"
          x={C + 5}
          y={C - mid(0) + 3}
          dominantBaseline="middle"
        >
          {startYear}
        </text>
        <text
          className="yr"
          x={C + 5}
          y={C - mid(n - 1) + 3}
          dominantBaseline="middle"
        >
          {endYear}
        </text>

        <g className="readout" aria-hidden="true">
          <text className="rc-big" x={C} y={C - 2} textAnchor="middle">
            {active ?? `${startYear}–${endYear}`}
          </text>
          <text className="rc-sub" x={C} y={C + 22} textAnchor="middle">
            {row ? `${row.heatwave_days} heatwave days` : "Hover or tap a ring"}
          </text>
          {row && (
            <text className="rc-sub" x={C} y={C + 40} textAnchor="middle">
              {row.events} {row.events === 1 ? "event" : "events"}
              {row.max_duration ? `, longest ${row.max_duration} days` : ""}
            </text>
          )}
        </g>

        {years.map((y, i) => (
          <circle
            key={y}
            className="hit"
            cx={C}
            cy={C}
            r={mid(i)}
            strokeWidth={pitch}
            onPointerEnter={() => setActive(y)}
            onPointerDown={() => setActive(y)}
          />
        ))}
      </svg>
      <figcaption>
        Each ring is a year, {startYear} in the middle to {endYear} on the
        outside. January is at the top. Every arc is a heatwave, and hotter
        spells glow brighter.
      </figcaption>
    </figure>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import MapPicker from "./MapPicker";
import { api } from "../api";
import { ordinal } from "../lib/format";

export const PLACES = [
  { name: "Delhi, India", lat: 28.61, lon: 77.21 },
  { name: "Ahmedabad, India", lat: 23.03, lon: 72.58 },
  { name: "Phoenix, USA", lat: 33.45, lon: -112.07 },
  { name: "Madrid, Spain", lat: 40.42, lon: -3.7 },
  { name: "Sydney, Australia", lat: -33.87, lon: 151.21 },
];

export function regionError(r, meta) {
  const n = (v) => Number(v);
  if (r.kind === "box") {
    const v = [r.south, r.west, r.north, r.east].map(n);
    if (v.some((x) => !Number.isFinite(x) || String(x) === ""))
      return "Fill in all four box edges.";
    const [s, w, no, e] = v;
    if (s < -90 || no > 90 || w < -180 || e > 180)
      return "Latitude must be within ±90 and longitude within ±180.";
    if (no <= s || e <= w)
      return "North must be greater than south, and east greater than west.";
    const max = meta.max_box_span_deg || 10;
    if (no - s > max || e - w > max)
      return `Keep each side of the box under ${max} degrees.`;
    if (no - s < 0.1 || e - w < 0.1)
      return "The box is too small. Make each side at least 0.1 degrees.";
    return "";
  }
  const la = n(r.lat);
  const lo = n(r.lon);
  if (!Number.isFinite(la) || !Number.isFinite(lo))
    return "Pick a place, drop a pin, or draw a box.";
  if (la < -90 || la > 90 || lo < -180 || lo > 180)
    return "Coordinates are out of range.";
  return "";
}

const coord = (lat, lon) =>
  `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`;

export default function QueryPanel({ form, setForm, meta, onRun, loading }) {
  const r = form.region;
  const [text, setText] = useState(r.name || "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searchMsg, setSearchMsg] = useState("");
  const [mode, setMode] = useState("pin");
  const [lookupError, setLookupError] = useState("");
  const [resolving, setResolving] = useState(false);
  const timer = useRef(null);
  const ctrl = useRef(null);

  useEffect(() => {
    setText(r.name || "");
    setLookupError("");
  }, [r.name]);

  const setRegion = (region) => setForm((f) => ({ ...f, region }));
  const err = regionError(r, meta);

  const onType = (e) => {
    const q = e.target.value;
    setText(q);
    clearTimeout(timer.current);
    ctrl.current?.abort();
    setSearchMsg("");
    if (q.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(async () => {
      const c = new AbortController();
      ctrl.current = c;
      try {
        const data = await api.geocode(q.trim(), c.signal);
        setResults(data.results);
        setOpen(true);
        if (!data.results.length)
          setSearchMsg(
            "No places found. Try a different spelling, or use the map.",
          );
      } catch (ex) {
        if (ex.name !== "AbortError") {
          setResults([]);
          setSearchMsg(ex.message);
          setOpen(true);
        }
      }
    }, 350);
  };

  const toRegion = (p) =>
    p.box
      ? { kind: "box", ...p.box, name: p.label }
      : { kind: "point", lat: p.lat, lon: p.lon, name: p.label };

  const choose = (p) => {
    setOpen(false);
    setResults([]);
    setSearchMsg("");
    setLookupError("");
    setRegion(toRegion(p));
  };

  // Pressing "Run analysis" with typed text that was never picked from the list:
  // look the text up and use the best match, so typing "Bhavnagar, India" just works.
  const submit = async (e) => {
    e.preventDefault();
    const typed = text.trim();
    if (typed.length >= 2 && typed !== (r.name || "")) {
      clearTimeout(timer.current);
      ctrl.current?.abort();
      setResolving(true);
      setLookupError("");
      try {
        const data = await api.geocode(typed);
        if (!data.results.length) {
          setLookupError(
            `No place found for “${typed}”. Check the spelling, or drop a pin on the map.`,
          );
          return;
        }
        setOpen(false);
        const next = { ...form, region: toRegion(data.results[0]) };
        setForm(next);
        onRun(next);
      } catch (ex) {
        setLookupError(ex.message);
      } finally {
        setResolving(false);
      }
      return;
    }
    if (!err) onRun();
  };

  const setBoxField = (k) => (e) =>
    setRegion({ ...r, [k]: e.target.value, name: "Custom box" });
  const toBox = () => {
    const lat = Number(r.lat),
      lon = Number(r.lon);
    setRegion({
      kind: "box",
      south: +(lat - 1).toFixed(2),
      north: +(lat + 1).toFixed(2),
      west: +(lon - 1).toFixed(2),
      east: +(lon + 1).toFixed(2),
      name: `Box around ${coord(lat, lon)}`,
    });
    setMode("box");
  };
  const toPoint = () => {
    const lat = +((Number(r.south) + Number(r.north)) / 2).toFixed(2);
    const lon = +((Number(r.west) + Number(r.east)) / 2).toFixed(2);
    setRegion({ kind: "point", lat, lon, name: coord(lat, lon) });
    setMode("pin");
  };

  const years = useMemo(() => {
    const out = [];
    for (let y = meta.min_year; y <= meta.max_year; y++) out.push(y);
    return out;
  }, [meta]);
  const gap = (meta.min_span_years || 10) - 1;
  const startOpts = years.filter((y) => y <= form.endYear - gap);
  const endOpts = years.filter((y) => y >= form.startYear + gap);
  const preset = (s, e) =>
    setForm((f) => ({
      ...f,
      startYear: Math.max(meta.min_year, s),
      endYear: Math.min(meta.max_year, e),
    }));

  return (
    <aside className="panel query" aria-label="Choose what to analyse">
      {/* Heatwave is the one hazard this app analyses, so it is shown as a fixed, selected label. */}
      <div className="hazards" role="group" aria-label="Hazard type">
        <span className="on">Heatwave</span>
      </div>

      <form onSubmit={submit}>
        <div className="field combo">
          <label htmlFor="place">Show heatwaves in</label>
          <input
            id="place"
            type="text"
            value={text}
            onChange={onType}
            onFocus={() => results.length && setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            placeholder="Search a city or state"
            autoComplete="off"
            maxLength={80}
            role="combobox"
            aria-expanded={open}
            aria-controls="place-list"
          />
          {open && (
            <ul id="place-list" className="suggest" role="listbox">
              {results.map((p, i) => (
                <li
                  key={`${p.id}-${i}`}
                  role="option"
                  aria-selected="false"
                  onMouseDown={() => choose(p)}
                >
                  {p.label}
                  <small>
                    {p.kind === "state"
                      ? "state or region, shown as a box"
                      : "city or place"}
                  </small>
                </li>
              ))}
              {!results.length && searchMsg && (
                <li className="msg">{searchMsg}</li>
              )}
            </ul>
          )}
        </div>
        <div className="chips" aria-label="Quick picks">
          {PLACES.map((p) => (
            <button
              type="button"
              key={p.name}
              className="chip"
              onClick={() =>
                setRegion({
                  kind: "point",
                  lat: p.lat,
                  lon: p.lon,
                  name: p.name,
                })
              }
            >
              {p.name.split(",")[0]}
            </button>
          ))}
        </div>

        {lookupError && (
          <p className="error" role="alert">
            {lookupError}
          </p>
        )}

        <div className="maptools">
          <div className="seg" role="group" aria-label="Map tool">
            <button
              type="button"
              aria-pressed={mode === "pin"}
              className={mode === "pin" ? "on" : ""}
              onClick={() => setMode("pin")}
            >
              Drop a pin
            </button>
            <button
              type="button"
              aria-pressed={mode === "box"}
              className={mode === "box" ? "on" : ""}
              onClick={() => setMode("box")}
            >
              Draw a box
            </button>
          </div>
          <span className="hint">
            {mode === "pin" ? "Click the map." : "Drag on the map."}
          </span>
        </div>
        <div className="mapframe">
          <MapPicker
            region={r}
            mode={mode}
            onPoint={(lat, lon) =>
              setRegion({
                kind: "point",
                lat: +lat.toFixed(2),
                lon: +lon.toFixed(2),
                name: coord(lat, lon),
              })
            }
            onBox={(b) =>
              setRegion({
                kind: "box",
                ...b,
                name: `Box ${b.south.toFixed(1)} to ${b.north.toFixed(1)}°, ${b.west.toFixed(1)} to ${b.east.toFixed(1)}°`,
              })
            }
          />
        </div>

        {r.kind === "box" ? (
          <fieldset className="box">
            <legend>Latitude and longitude box</legend>
            {["north", "south", "west", "east"].map((k) => (
              <label key={k}>
                {k[0].toUpperCase() + k.slice(1)}
                <input
                  type="number"
                  step="0.1"
                  value={r[k]}
                  onChange={setBoxField(k)}
                />
              </label>
            ))}
            <button type="button" className="link" onClick={toPoint}>
              Use a single point instead
            </button>
          </fieldset>
        ) : (
          <p className="coords">
            {Number.isFinite(Number(r.lat))
              ? coord(Number(r.lat), Number(r.lon))
              : "No point chosen"}{" "}
            <button type="button" className="link" onClick={toBox}>
              Use a box around this point
            </button>
          </p>
        )}
        {err && (
          <p className="error" role="alert">
            {err}
          </p>
        )}

        <div className="sentence">
          <span>from</span>
          <select
            aria-label="Start year"
            value={form.startYear}
            onChange={(e) => setForm({ ...form, startYear: +e.target.value })}
          >
            {startOpts.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
          <span>to</span>
          <select
            aria-label="End year"
            value={form.endYear}
            onChange={(e) => setForm({ ...form, endYear: +e.target.value })}
          >
            {endOpts.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
        </div>
        <div className="chips">
          <button
            type="button"
            className="chip"
            onClick={() => preset(1990, 2020)}
          >
            1990 to 2020
          </button>
          <button
            type="button"
            className="chip"
            onClick={() => preset(meta.max_year - 29, meta.max_year)}
          >
            Last 30 years
          </button>
          <button
            type="button"
            className="chip"
            onClick={() => preset(1980, meta.max_year)}
          >
            Since 1980
          </button>
        </div>

        <div className="sentence">
          <span>A hot day is above the</span>
          <select
            aria-label="Percentile"
            value={form.percentile}
            onChange={(e) => setForm({ ...form, percentile: +e.target.value })}
          >
            {[90, 92, 95, 97, 99].map((p) => (
              <option key={p} value={p}>
                {ordinal(p)}
              </option>
            ))}
          </select>
          <span>percentile. A heatwave is</span>
          <select
            aria-label="Minimum days"
            value={form.minDays}
            onChange={(e) => setForm({ ...form, minDays: +e.target.value })}
          >
            {[2, 3, 4, 5, 6, 7].map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <span>or more hot days in a row.</span>
        </div>

        <fieldset className="radios">
          <legend>Threshold</legend>
          <label>
            <input
              type="radio"
              name="method"
              checked={form.method === "fixed"}
              onChange={() => setForm({ ...form, method: "fixed" })}
            />{" "}
            One value for the whole period
          </label>
          <label>
            <input
              type="radio"
              name="method"
              checked={form.method === "calendar"}
              onChange={() => setForm({ ...form, method: "calendar" })}
            />{" "}
            A value for each day of the year
          </label>
        </fieldset>

        <button type="submit" className="run" disabled={loading || !!err}>
          {loading ? "Analysing…" : "Run analysis"}
        </button>
      </form>
    </aside>
  );
}

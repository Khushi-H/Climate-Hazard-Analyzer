import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import QueryPanel, { PLACES, regionError } from "./components/QueryPanel";
import Stripes from "./components/Stripes";
import Hero from "./components/Hero";
import TrendChart from "./components/TrendChart";
import HeatCalendar from "./components/HeatCalendar";
import Ledger from "./components/Ledger";
import Robustness from "./components/Robustness";
import EventsTable from "./components/EventsTable";
import Quality from "./components/Quality";
import Notes from "./components/Notes";
import Exports from "./components/Exports";
import ChartViewer from "./components/ChartViewer";

const DEFAULT_META = {
  min_year: 1950,
  max_year: new Date().getFullYear() - 1,
  min_span_years: 10,
  max_box_span_deg: 10,
  hazards: [{ id: "heatwave", label: "Heatwave", available: true }],
};
const DEFAULTS = {
  region: {
    kind: "point",
    lat: PLACES[0].lat,
    lon: PLACES[0].lon,
    name: PLACES[0].name,
  },
  startYear: 1990,
  endYear: 2020,
  percentile: 95,
  minDays: 3,
  method: "fixed",
};

function readUrl() {
  const q = new URLSearchParams(window.location.search);
  const f = structuredClone(DEFAULTS);
  const num = (k) =>
    q.has(k) && Number.isFinite(Number(q.get(k))) ? Number(q.get(k)) : null;
  if (["south", "west", "north", "east"].every((k) => num(k) != null))
    f.region = {
      kind: "box",
      south: num("south"),
      west: num("west"),
      north: num("north"),
      east: num("east"),
      name: (q.get("name") || "Custom box").slice(0, 80),
    };
  else if (num("lat") != null && num("lon") != null)
    f.region = {
      kind: "point",
      lat: num("lat"),
      lon: num("lon"),
      name: (q.get("name") || "").slice(0, 80),
    };
  if (num("start_year")) f.startYear = num("start_year");
  if (num("end_year")) f.endYear = num("end_year");
  if (num("percentile")) f.percentile = num("percentile");
  if (num("min_days")) f.minDays = num("min_days");
  if (["fixed", "calendar"].includes(q.get("method")))
    f.method = q.get("method");
  return f;
}

function writeUrl(form) {
  const q = new URLSearchParams();
  const r = form.region;
  if (r.kind === "box")
    ["south", "west", "north", "east"].forEach((k) => q.set(k, r[k]));
  else {
    q.set("lat", r.lat);
    q.set("lon", r.lon);
  }
  if (r.name) q.set("name", r.name);
  q.set("start_year", form.startYear);
  q.set("end_year", form.endYear);
  q.set("percentile", form.percentile);
  q.set("min_days", form.minDays);
  q.set("method", form.method);
  window.history.replaceState(null, "", `?${q.toString()}`);
}

export default function App() {
  const [meta, setMeta] = useState(DEFAULT_META);
  const [form, setForm] = useState(readUrl);
  const [analysis, setAnalysis] = useState(null);
  const [applied, setApplied] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState("heatwave_days");
  const [runId, setRunId] = useState(0);
  const [viewing, setViewing] = useState(false);
  const ctrl = useRef(null);

  const run = useCallback(async (f) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setLoading(true);
    setError("");
    try {
      const data = await api.analysis(f, c.signal);
      setAnalysis(data);
      setApplied(structuredClone(f));
      setRunId((n) => n + 1);
      writeUrl(f);
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      if (ctrl.current === c) setLoading(false);
    }
  }, []);

  useEffect(() => {
    api
      .meta()
      .then((m) => setMeta({ ...DEFAULT_META, ...m }))
      .catch(() => {});
    if (!regionError(form.region, DEFAULT_META)) run(form);
    // run once on load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const a = analysis;
  return (
    <div className="page">
      <header className="top">
        <div className="shell top-in">
          <div className="brand">
            <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
              <rect width="32" height="32" rx="8" fill="#0a1330" />
              <rect x="6" y="8" width="4" height="16" fill="#5b9bd5" />
              <rect x="12" y="8" width="4" height="16" fill="#e6eaee" />
              <rect x="18" y="8" width="4" height="16" fill="#ef8a62" />
              <rect x="24" y="8" width="3" height="16" fill="#b2182b" />
            </svg>
            <span>Heatline</span>
          </div>
          {a && applied && (
            <Exports form={applied} onChart={() => setViewing(true)} />
          )}
        </div>
      </header>

      <div className={`stripe-band ${loading ? "busy" : ""}`}>
        {a ? (
          <Stripes yearly={a.yearly} animateKey={runId} />
        ) : (
          <div className="stripe-empty" />
        )}
        <p className="stripe-cap shell">
          {a
            ? `Each stripe is one year, ${a.yearly[0].year} to ${a.yearly[a.yearly.length - 1].year}. Blue years had cooler daily highs than the period average, red years hotter.`
            : loading
              ? "Fetching decades of daily temperatures. A new place can take up to a minute."
              : "Pick a place and run the analysis."}
        </p>
      </div>

      {(a || loading || !error) && (
        <div className="hero-band">
          {a && <Hero key={runId} analysis={a} />}
          {!a && !loading && !error && (
            <section className="shell hero-empty">
              <h1>
                How much hotter are the hottest spells getting where you live?
              </h1>
            </section>
          )}
          {!a && loading && (
            <section className="shell hero-empty">
              <h1>Reading the record{"…"}</h1>
            </section>
          )}
        </div>
      )}

      <main className="shell split">
        <QueryPanel
          form={form}
          setForm={setForm}
          meta={meta}
          onRun={(f) => run(f || form)}
          loading={loading}
        />
        <div
          className={`results ${loading && a ? "dim" : ""}`}
          aria-busy={loading}
        >
          {error && (
            <div className="panel alert" role="alert">
              <h2>The analysis did not run</h2>
              <p>{error}</p>
              <button className="link" onClick={() => run(form)}>
                Try again
              </button>
            </div>
          )}
          {a && (
            <>
              <TrendChart analysis={a} metric={metric} setMetric={setMetric} />
              <HeatCalendar
                events={a.events}
                startYear={a.params.start_year}
                endYear={a.params.end_year}
              />
              <Ledger analysis={a} metric={metric} />
              <Robustness robustness={a.robustness} />
              <div className="two">
                <EventsTable events={a.events} />
                <Quality analysis={a} />
              </div>
              <Notes insights={a.insights} />
            </>
          )}
        </div>
      </main>

      <footer className="shell foot">
        <p>
          Daily maximum temperature from the Open-Meteo Historical Weather API
          (ERA5-Land reanalysis, Copernicus Climate Change Service, CC BY 4.0).
          Heatwave = at least N days in a row above a percentile threshold. Map
          tiles &copy; OpenStreetMap contributors.
        </p>
      </footer>

      {viewing && applied && (
        <ChartViewer
          form={applied}
          metric={metric}
          onClose={() => setViewing(false)}
        />
      )}
    </div>
  );
}

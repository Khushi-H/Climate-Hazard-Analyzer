import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { METRIC_TABS } from "./TrendChart";

const FOCUSABLE =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Full-screen view of the server-rendered chart image. The Back button, the Escape key and the
// browser's own Back button all return to the results page exactly as it was left.
export default function ChartViewer({ form, metric: initialMetric, onClose }) {
  const [metric, setMetric] = useState(initialMetric);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [attempt, setAttempt] = useState(0);
  const root = useRef(null);
  const backBtn = useRef(null);

  const close = useCallback(() => {
    if (window.history.state && window.history.state.chartViewer)
      window.history.back();
    else onClose();
  }, [onClose]);

  // One history entry while the viewer is open, so the browser Back button closes it too.
  useEffect(() => {
    if (!(window.history.state && window.history.state.chartViewer)) {
      window.history.pushState({ chartViewer: true }, "");
    }
    const onPop = () => onClose();
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [onClose]);

  // Lock page scroll, move focus into the viewer, and give focus back when it closes.
  useEffect(() => {
    const opener = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    backBtn.current?.focus();
    return () => {
      document.body.style.overflow = prevOverflow;
      if (opener && typeof opener.focus === "function") opener.focus();
    };
  }, []);

  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    if (e.key !== "Tab" || !root.current) return;
    const items = [...root.current.querySelectorAll(FOCUSABLE)];
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const label = METRIC_TABS.find(([id]) => id === metric)?.[1] || "Chart";
  const base = api.plotUrl(form, metric);
  const src = attempt ? `${base}&retry=${attempt}` : base;
  const place = form.region.name || "Selected region";
  const file = `heatline-${metric}-${form.startYear}-${form.endYear}.png`;

  const pick = (id) => {
    if (id === metric) return;
    setStatus("loading");
    setMetric(id);
  };

  return (
    <div
      className="viewer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="viewer-title"
      ref={root}
      onKeyDown={onKeyDown}
    >
      <div className="viewer-bar">
        <button
          type="button"
          className="viewer-back"
          onClick={close}
          ref={backBtn}
        >
          <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="M12.5 4 6.5 10l6 6"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Back to results
        </button>
        <div className="viewer-title">
          <h2 id="viewer-title">{label} per year</h2>
          <p>
            {place}, {form.startYear} to {form.endYear}
          </p>
        </div>
        <div className="tabs viewer-tabs" role="group" aria-label="Measure">
          {METRIC_TABS.map(([id, text]) => (
            <button
              key={id}
              type="button"
              aria-pressed={metric === id}
              className={metric === id ? "on" : ""}
              onClick={() => pick(id)}
            >
              {text}
            </button>
          ))}
        </div>
        <a className="viewer-save" href={src} download={file}>
          Download PNG
        </a>
      </div>

      <div className="viewer-stage">
        <figure className="viewer-sheet" data-status={status}>
          {status === "error" ? (
            <div className="viewer-error" role="alert">
              <p>The chart image could not be loaded.</p>
              <button
                type="button"
                className="link"
                onClick={() => {
                  setStatus("loading");
                  setAttempt((n) => n + 1);
                }}
              >
                Try again
              </button>
            </div>
          ) : (
            <img
              key={src}
              src={src}
              alt={`${label} per year for ${place}, ${form.startYear} to ${form.endYear}, with a rolling mean and a linear fit.`}
              onLoad={() => setStatus("ready")}
              onError={() => setStatus("error")}
            />
          )}
        </figure>
        <p className="viewer-hint">
          Scroll sideways to see the whole chart at a readable size.
        </p>
      </div>
    </div>
  );
}

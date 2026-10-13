import { api } from "../api";

// The chart image opens in an in-app viewer (with a Back button) instead of a bare image in a new tab.
export default function Exports({ form, onChart }) {
  return (
    <nav className="exports" aria-label="Download results">
      <a href={api.pdfUrl(form)} download>
        PDF report
      </a>
      <a href={api.csvUrl(form, "yearly")} download>
        Yearly CSV
      </a>
      <a href={api.csvUrl(form, "events")} download>
        Events CSV
      </a>
      <button type="button" onClick={onChart}>
        Chart image
      </button>
    </nav>
  );
}

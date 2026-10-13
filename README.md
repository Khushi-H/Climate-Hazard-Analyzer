# Heatline: Climate Hazard Trend Analyzer

A full-stack web app that shows how **heatwave** frequency, length and intensity have changed for any city, state or custom lat-lon box over a chosen time range, with statistically honest summaries.

- **Frontend:** React 18 + Vite, Chart.js (trend charts), a custom canvas calendar, Leaflet (map region selection)
- **Backend:** Python, FastAPI, pandas / NumPy / SciPy
- **Database (NoSQL):** MongoDB (cache of raw weather, computed analyses and geocoding)
- **Data source:** Open-Meteo Historical Weather API (ERA5-Land reanalysis from Copernicus, pinned with `models=era5_land`), no API key needed
- **Bonus challenges, all done:** Leaflet map UI (pin and draw-a-box), PDF and CSV export, Mann-Kendall test with Sen's slope alongside linear regression

> Deployed app: **<add your URL here>** | Demo video (optional): **<add link here>**

---

## 1. Run it locally

You need **Python 3.10+** and **Node.js 18+**. MongoDB is optional for a first run (see below).

### Backend (terminal 1)

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` first.

Check it: open http://localhost:8000/api/health and http://localhost:8000/docs (interactive API docs).

### Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` to port 8000, so no extra config is needed.

### MongoDB

With `MONGO_URI` empty in `backend/.env`, the app uses an **in-memory MongoDB (mongomock)**. Everything works, but the cache is lost on restart. For real persistence use one of:

```bash
docker run -d --name mongo -p 27017:27017 mongo:7      # local MongoDB
# then in backend/.env:  MONGO_URI=mongodb://localhost:27017
```

or a free MongoDB Atlas M0 cluster (`MONGO_URI=mongodb+srv://USER:PASS@cluster.../`). `GET /api/health` shows which database is in use.

Or run backend + MongoDB together with Docker: `docker compose up --build`, then open http://localhost:8000 (the container also serves the built React app).

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

41 tests cover cleaning, threshold and event detection, Mann-Kendall (known values), the full pipeline on noisy synthetic data, input validation, caching, ETag, exports, sanitising, rate limiting, upstream failure, a regression test that the weather model stays pinned, and the robustness check (every cell recounted with plain loops and scipy's own Theil-Sen and Kendall). If a `MONGO_URI` in `.env` points to a MongoDB that is not running, set `MONGO_URI=` (empty) for the test run so the in-memory database is used.

### Check the numbers independently

`backend/verify_data.py` downloads the raw daily maximum temperature straight from Open-Meteo, detects heatwaves with plain Python loops (none of the app's code) and compares the result, year by year, with what the running backend returns.

```bash
cd backend
python verify_data.py --lat 21.76 --lon 72.15 --start 2000 --end 2020
```

It prints the threshold, the number of events and one row per year (`yes` / `DIFF`). It then recounts every cell of the robustness grid (events, heatwave days and Sen's slope, with its own plain-Python median of pairwise slopes) and ends with `RESULT: all years and all robustness cells match.` when the app and the independent count agree. It checks the detection and counting logic, not the upstream data itself. The first five raw days are printed so they can be compared by hand with open-meteo.com.

### Production build (single service)

```bash
cd frontend && npm run build        # creates frontend/dist
cd ../backend && uvicorn app.main:app --port 8000
```

If `frontend/dist` exists, FastAPI serves it, so one URL serves both the UI and the API.

---

## 2. Architecture

```
React (Vite)  --->  FastAPI  ---> MongoDB
 Leaflet map         |  rate limit + validation        weather_cache   raw daily Tmax (TTL 30 d)
 Chart.js            |  analysis orchestrator          analyses        events, yearly metrics, trends, insights (TTL 30 d)
 canvas calendar     |  cleaning -> hazards -> trends  geocode_cache   place search results (TTL 7 d)
                     '--> Open-Meteo archive + geocoding (allow-listed hosts only)
```

Request flow for `GET /api/analysis`:

1. Validate and normalise parameters (ranges, box size, years, percentile). Round coordinates to 0.01 degrees.
2. Build a cache key (region points, years, percentile, min days, method, algorithm version).
3. **Hit:** read the stored analysis from MongoDB and return it. **Miss:** fetch daily Tmax (or reuse the cached raw series), clean it, detect events, compute trends, **store the result in MongoDB, then read it back from MongoDB** and return JSON.

| Endpoint                                                                                                                | Purpose                                 |
| ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `GET /api/health`                                                                                                       | status and which database is active     |
| `GET /api/meta`                                                                                                         | year limits, hazard list, metric list   |
| `GET /api/geocode?q=`                                                                                                   | city / state search (cached)            |
| `GET /api/analysis?lat=&lon=` or `?south=&west=&north=&east=` plus `start_year, end_year, percentile, min_days, method` | full analysis JSON                      |
| `GET /api/analysis/export.csv?kind=yearly\|events`                                                                      | CSV export                              |
| `GET /api/analysis/export.pdf`                                                                                          | PDF report with trend plots             |
| `GET /api/analysis/plot.png?metric=`                                                                                    | server-rendered trend plot (matplotlib) |

```
backend/app
  main.py        app, middleware, error handlers, optional static hosting
  routes.py      endpoints and input validation
  security.py    sliding-window rate limiter, security headers
  schemas.py     Region and AnalysisParams (validated, hashable, cache keys)
  db.py          MongoDB / mongomock, TTL indexes
  services/
    openmeteo.py   upstream client (allow-list, retries, size cap, unit conversion)
    ingest.py      raw-data cache
    cleaning.py    gaps, outliers, duplicates, units
    hazards.py     threshold + heatwave detection + yearly metrics
    trends.py      regression, Mann-Kendall, Sen's slope, rolling mean
    robustness.py  re-runs the trend for stricter / looser heatwave definitions
    insights.py    honest plain-language summaries
    analysis.py    orchestration
    exports.py     CSV, PNG, PDF
frontend/src       App, api client, components (QueryPanel, MapPicker, Stripes, TrendChart, HeatCalendar, Ledger, Robustness ...)
```

---

## 3. Data source

**Open-Meteo Historical Weather API** (`archive-api.open-meteo.com`), variable `temperature_2m_max`, daily, local time zone. It serves ERA5-Land reanalysis (`models=era5_land`, 0.1 degree grid, about 9 km) from the Copernicus Climate Change Service (CC BY 4.0), so there are no station gaps in the usual sense, but the data is gridded. Place search uses Open-Meteo Geocoding.

**Why the model is pinned:** Open-Meteo's default "best match" blends ERA5-Land with a different forecast-system model (IFS HRES, 9 km) from 2017 onwards. Mixing two models inside one series creates a fake step change around 2017 (in testing, one location jumped from 10 to 74 heatwave days between 2016 and 2017, and the trend vanished once the model was pinned). Open-Meteo's own documentation recommends only ERA5 / ERA5-Land for multi-decade climate analysis. Set `HISTORICAL_MODEL=era5` in `backend/.env` for the 0.25 degree ERA5 instead. The model is part of the cache key, so data from different models is never mixed.

- A **point** uses one grid cell. A **box** (or a state, which is approximated as a 2 x 2 degree box around its centroid) is sampled on a **2 x 2 grid** of points and the daily values are averaged.
- Only complete past years are offered (the latest complete year), from 1950.

## 4. Hazard logic (heatwave)

A **heatwave** is a run of at least `min_days` (default **3**) consecutive days whose maximum temperature is above the `percentile` (default **95th**) threshold.

Two threshold methods (selectable):

- **One value for the whole period** (default, matches the brief): the percentile of all daily maxima in the selected period.
- **A value for each day of the year:** percentile within a +-7 day window around each calendar day, which is the usual seasonal definition and also flags warm spells outside the hot season.

Per year the app records: number of events, heatwave days, longest event, mean duration, mean intensity (average degrees above threshold), peak temperature, hot days, mean daily high and data coverage.

**Trend analysis** (for heatwave days, events, longest event and intensity): linear regression (slope, R2, p), **Mann-Kendall** test with tie correction, **Sen's slope**, 5-year centred rolling mean, and first-N vs last-N years change (N = 10, or a third of the record if shorter). The headline sentence (for example "Heatwave days increased by 40% ...") always states whether the trend is statistically significant.

### Robustness check: does the definition change the answer?

"Hot" (which percentile) and "wave" (how many days in a row) have no single correct value, and a trend that only shows up for one convenient pair of values is not a finding. After the main analysis, the same cleaned record is re-analysed on a grid of **percentile (90, 95, 97) x minimum length (2, 3, 5 days)**. The user's own setting is always added to the grid and marked "your setting". Each cell gets the same statistics as the headline (Sen's slope per decade, Mann-Kendall p-value, first-vs-last change), and a one-sentence verdict says whether all cells agree (`consistent`), most do (`mostly`) or the answer depends on the definition (`mixed`). Cells with fewer than 10 events are flagged because their trend estimate is fragile.

It costs no extra download (the cleaned series is reused), it is stored in the same MongoDB analysis document (`robustness` in the JSON), and it appears in the app ("Does the definition change the answer?") and in the PDF report. If it ever fails, the main analysis is still returned.

## 5. Data handling and cleaning

Real data is messy, so the pipeline is explicit and reports what it did (shown in the "Data quality" panel):

- re-index to a complete daily calendar (exposes silently missing dates), drop duplicates
- remove physically impossible values (outside -70..60 deg C)
- remove isolated spikes (a single day more than max(12 deg C, 6 x MAD) from the 15-day rolling median and from both neighbouring days). Real heatwave days have hot neighbours, so genuine peaks are never removed
- interpolate gaps of **3 days or fewer**; longer gaps stay missing, **break a run, and are never counted as hot**
- unit check on the provider response (deg F / K converted to deg C)
- years with under 80% valid days are flagged and **excluded from trends**

## 6. Security and performance

- **Input safety:** every parameter is range-checked (lat/lon, years 1950..last complete year, at least 10 years, percentile 80-99.5, box side 0.1-10 degrees), NaN/inf rejected, labels stripped of control characters and markup, CSV contains only numbers and dates (no formula injection), PDF text is sanitised.
- **Safe external access:** only two fixed Open-Meteo hosts can ever be contacted (no user-supplied URLs), redirects are not followed, timeouts, response size cap, retries with backoff, upstream failures return a clean 502.
- **Rate limiting:** per-IP sliding window (120/min general, 20/min analysis and export, 30/min geocode), `Retry-After` header on 429. Set `TRUST_PROXY=1` only behind a trusted proxy.
- **Caching:** raw weather, computed analyses and geocoding in MongoDB with TTL indexes; per-key locks stop duplicate upstream calls; ETag / 304 and `Cache-Control` on responses; in-process LRU for rendered PNG/PDF; GZip.
- Security headers (`nosniff`, `X-Frame-Options`, referrer and permissions policy); CORS restricted to configured origins; no secrets in code (`.env`).

## 7. Assumptions

- The percentile threshold is computed from the **same period being analysed**, so results show change _within_ the period, not versus an official climate-normal baseline (stated in the app's caveats).
- Heatwaves are attributed to the year in which they **start**.
- A state is approximated as a 2 x 2 degree box (the geocoder only gives a centroid). Boxes crossing the antimeridian are not supported.
- Reanalysis data is used as the "truth"; it smooths local extremes and urban heat islands.
- Only the **heatwave** hazard is implemented, as the brief asks ("a working heatwave analysis beats a half-finished multi-hazard app"). It is shown as the fixed, selected hazard; the code is structured so another hazard module can be added next to `hazards.py`.

## 8. What I would improve with more time

- Add drought (SPI or consecutive dry days) and heavy rainfall (R95p) using the same pipeline.
- Use a fixed 1991-2020 WMO baseline option, and real administrative boundaries for states (GeoJSON) with area-weighted sampling.
- Humidity-aware heat metrics (wet-bulb or heat index), and absolute-threshold definitions such as the IMD 40 deg C rule.
- Background jobs (Celery or RQ) with progress for very large boxes, and Redis for the rate limiter and cache across several instances.
- Frontend tests (Vitest, Playwright), request-level metrics, and a CI pipeline.

## 9. Deploying (free tier)

**Single service on Render (simplest):** push to GitHub, create a free MongoDB Atlas cluster, then on Render choose _New > Blueprint_ (uses `render.yaml` and the root `Dockerfile`) and set `MONGO_URI`. The container builds the React app and serves it together with the API on one URL.

**Split deployment:** backend on Render / Cloud Run, frontend on Vercel or Netlify with `VITE_API_BASE=https://your-backend-url` and the frontend URL added to the backend `CORS_ORIGINS`.

## 10. AI tools used

- **Claude (Anthropic, via claude.ai):** generated the initial project scaffold, backend modules, tests and frontend components from the case-study brief; I reviewed the code, ran the test suite and the production build, and can walk through and change any part of it live.
- **Claude (review pass):** cross-checked the numbers shown in the app and in the exported PDF, yearly CSV, events CSV and chart image for one location (Bhavnagar, 2000-2020) against each other and against an independent recomputation, and fixed the issues it found (unit labels, chart legend wording, PDF page break). I re-ran the tests and `verify_data.py` myself.

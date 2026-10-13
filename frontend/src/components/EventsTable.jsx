import { useMemo, useState } from 'react'
import { fmtDate } from '../lib/format'

const SORTS = {
  duration: ['Longest', (a, b) => b.duration - a.duration],
  peak_temp: ['Hottest', (a, b) => b.peak_temp - a.peak_temp],
  severity: ['Most severe', (a, b) => b.severity - a.severity],
  start: ['Most recent', (a, b) => (a.start < b.start ? 1 : -1)],
}

export default function EventsTable({ events }) {
  const [sort, setSort] = useState('severity')
  const rows = useMemo(() => [...events].sort(SORTS[sort][1]).slice(0, 10), [events, sort])
  return (
    <section className="panel" aria-labelledby="ev-h">
      <div className="panel-head">
        <h2 id="ev-h">Biggest heatwaves</h2>
        <div className="tabs" role="group" aria-label="Sort events">
          {Object.entries(SORTS).map(([k, [label]]) => (
            <button key={k} aria-pressed={sort === k} className={sort === k ? 'on' : ''} onClick={() => setSort(k)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="empty">No heatwaves met the definition for this region and period. Try a lower percentile or a shorter minimum length.</p>
      ) : (
        <div className="table-wrap" tabIndex={0}>
          <table className="data">
            <thead>
              <tr><th>Started</th><th>Ended</th><th>Days</th><th>Peak {'°C'}</th><th>Above threshold</th><th>Severity</th></tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.start}>
                  <td>{fmtDate(e.start)}</td>
                  <td>{fmtDate(e.end)}</td>
                  <td>{e.duration}</td>
                  <td>{e.peak_temp.toFixed(1)}</td>
                  <td>+{e.intensity.toFixed(1)} {'°C'}</td>
                  <td>{e.severity.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="note">Severity adds up how many degrees each day was above the threshold.</p>
    </section>
  )
}

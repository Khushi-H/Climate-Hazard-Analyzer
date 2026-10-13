export default function Quality({ analysis }) {
  const q = analysis.quality
  const up = analysis.meta.upstream || {}
  return (
    <section className="panel" aria-labelledby="q-h">
      <div className="panel-head">
        <h2 id="q-h">Data quality</h2>
        <p className="sub">What was fixed or removed before analysis.</p>
      </div>
      <div className="meter" role="img" aria-label={`${q.completeness_pct}% of days have valid data`}>
        <div style={{ width: `${q.completeness_pct}%` }} />
      </div>
      <p className="meter-label"><b>{q.completeness_pct.toFixed(1)}%</b> of {q.total_days.toLocaleString()} days have valid data</p>
      <dl className="mini">
        <div><dt>Missing in source</dt><dd>{q.missing_raw}</dd></div>
        <div><dt>Gaps of 3 days or fewer filled</dt><dd>{q.interpolated}</dd></div>
        <div><dt>Impossible values removed</dt><dd>{q.out_of_range_removed}</dd></div>
        <div><dt>Spikes removed</dt><dd>{q.spikes_removed}</dd></div>
        <div><dt>Still missing (never counted as hot)</dt><dd>{q.remaining_missing}</dd></div>
      </dl>
      <p className="note">
        Source: {analysis.meta.source}. Values were read in {up.units_in || '°C'} and converted to {'°C'} where needed.
        {analysis.cache ? ` Served from ${analysis.cache.analysis === 'hit' ? 'the database cache' : 'a fresh download, now cached'}.` : ''}
      </p>
    </section>
  )
}

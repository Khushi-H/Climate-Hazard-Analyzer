export default function Notes({ insights }) {
  return (
    <section className="notes" aria-labelledby="n-h">
      <div>
        <h2 id="n-h">What the data says</h2>
        <ul>
          {insights.bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      </div>
      <div>
        <h2>How far to trust it</h2>
        <ul>
          {insights.caveats.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}

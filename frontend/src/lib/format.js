export const signed = (n, d = 1) =>
  n == null || Number.isNaN(n) ? '-' : `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(d)}`

export const num = (n, d = 1) => (n == null || Number.isNaN(n) ? '-' : Number(n).toFixed(d))

export const fmtDate = (iso) => {
  const d = new Date(iso + 'T00:00:00Z')
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export const pValue = (p) => (p == null ? '-' : p < 0.001 ? '< 0.001' : p.toFixed(3))

// 1st, 2nd, 3rd, 4th ... (11th, 12th, 13th are the exceptions); non-integers keep a plain "th"
export const ordinal = (n) => {
  const v = Number(n)
  if (!Number.isInteger(v)) return `${v}th`
  const t = v % 100
  if (t >= 11 && t <= 13) return `${v}th`
  return `${v}${{ 1: 'st', 2: 'nd', 3: 'rd' }[v % 10] || 'th'}`
}
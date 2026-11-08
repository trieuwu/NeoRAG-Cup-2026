import type { Citation } from './types'

// ---------------------------------------------------------------- số và thời gian

export const grp = (n: number) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0')
export const ms = (n: number) => `${grp(n)} ms`
export const sec = (n: number) => `${(n / 1000).toFixed(2).replace('.', ',')} s`
export const usd = (n: number) => `$${n.toFixed(4)}`

// ---------------------------------------------------------------- CLB

export type ClubKey = 'pro' | 'mm' | 'gcc' | 's2b'
export interface ClubInfo {
  key: ClubKey
  label: string
  cls: string
}

const CLUBS: Record<ClubKey, ClubInfo> = {
  pro: { key: 'pro', label: 'ProPTIT', cls: 'club--pro' },
  mm: { key: 'mm', label: 'Multimedia', cls: 'club--mm' },
  gcc: { key: 'gcc', label: 'GCC', cls: 'club--gcc' },
  s2b: { key: 's2b', label: 'S2B', cls: 'club--s2b' },
}

/** Tên CLB trong corpus ("CLB Lập Trình PTIT"...) hoặc khóa của bước viết lại ("proptit"...) → nhãn ngắn. */
export function club(name: string | null | undefined): ClubInfo {
  const n = (name ?? '').toLowerCase()
  if (n.includes('lập trình') || n.includes('proptit')) return CLUBS.pro
  if (n.includes('multimedia') || n === 'mm' || n.includes('mpc')) return CLUBS.mm
  if (n.includes('game') || n.includes('gcc')) return CLUBS.gcc
  return CLUBS.s2b
}

// ---------------------------------------------------------------- câu trả lời có trích dẫn

export type Segment = { t: 'text'; s: string } | { t: 'cite'; n: number }

/** Tách "… [1][3]" thành đoạn văn và số trích dẫn. */
export function segments(answer: string): Segment[] {
  const out: Segment[] = []
  const re = /\[(\d+)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(answer))) {
    if (m.index > last) out.push({ t: 'text', s: answer.slice(last, m.index) })
    out.push({ t: 'cite', n: Number(m[1]) })
    last = m.index + m[0].length
  }
  if (last < answer.length) out.push({ t: 'text', s: answer.slice(last) })
  return out
}

/** Bỏ dấu [n] để sao chép câu trả lời. */
export const plainAnswer = (answer: string) => answer.replace(/\s*\[\d+\]/g, '').trim()

/** Đánh dấu trong đoạn nguồn các con số/ngày và cụm từ dài cũng xuất hiện trong câu trả lời. */
export function highlight(text: string, answer: string): { s: string; h: boolean }[] {
  const plain = plainAnswer(answer).toLowerCase()
  const terms = new Set<string>()
  for (const m of plain.matchAll(/\d+(?:[/.:]\d+)*/g)) if (m[0].length >= 2) terms.add(m[0])
  for (const m of plain.matchAll(/"([^"]{4,})"|“([^”]{4,})”/g)) terms.add((m[1] ?? m[2]).toLowerCase())
  if (!terms.size) return [{ s: text, h: false }]
  const escaped = [...terms].sort((a, b) => b.length - a.length).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`(${escaped.join('|')})`, 'gi')
  return text
    .split(re)
    .filter(Boolean)
    .map((s) => ({ s, h: terms.has(s.toLowerCase()) }))
}

export const citationAria = (c: Citation) => `Nguồn ${c.n}: ${club(c.club).label}, đoạn ${c.id}`

// ---------------------------------------------------------------- JSON tô màu

export function tokenizeJsonLine(line: string): { t: string; cls: string }[] {
  const re =
    /("(?:\\.|[^"\\])*")(\s*:)?|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)|\b(true|false|null)\b|([{}[\],:])|(\s+)|([^\s])/g
  const out: { t: string; cls: string }[] = []
  let m: RegExpExecArray | null
  while ((m = re.exec(line))) {
    if (m[1] !== undefined) {
      if (m[2]) {
        out.push({ t: m[1], cls: 'tk-key' })
        out.push({ t: m[2], cls: 'tk-pun' })
      } else out.push({ t: m[1], cls: 'tk-str' })
    } else if (m[3] !== undefined) out.push({ t: m[3], cls: 'tk-num' })
    else if (m[4] !== undefined) out.push({ t: m[4], cls: 'tk-bool' })
    else out.push({ t: m[0], cls: 'tk-pun' })
  }
  return out
}

/** JSON gọn: mảng object in mỗi phần tử một dòng (bảng 20 ứng viên vẫn đọc được). */
export function prettyJson(o: unknown, ind = 0): string[] {
  const pad = '  '.repeat(ind)
  if (Array.isArray(o)) {
    if (!o.length) return ['[]']
    if (o.every((x) => x && typeof x === 'object')) {
      return ['[', ...o.map((x, i) => `${pad}  ${JSON.stringify(x)}${i < o.length - 1 ? ',' : ''}`), `${pad}]`]
    }
    return [JSON.stringify(o)]
  }
  if (o && typeof o === 'object') {
    const keys = Object.keys(o)
    let out = ['{']
    keys.forEach((k, i) => {
      const sub = prettyJson((o as Record<string, unknown>)[k], ind + 1)
      sub[0] = `${pad}  ${JSON.stringify(k)}: ${sub[0]}`
      if (i < keys.length - 1) sub[sub.length - 1] += ','
      out = out.concat(sub)
    })
    out.push(`${pad}}`)
    return out
  }
  return [JSON.stringify(o)]
}

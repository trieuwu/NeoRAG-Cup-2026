import { useEffect, useMemo, useRef, useState } from 'react'
import { club, grp, highlight, ms, prettyJson, tokenizeJsonLine, usd } from '../lib/format'
import type { BotMsg } from '../lib/model'
import type { Candidate } from '../lib/types'
import { shownCitations } from './BotMessage'
import { Icon } from './Icon'

export type PanelKind = 'sources' | 'tech' | null
export type TechTab = 'query' | 'retrieval' | 'time' | 'json'

const TABS: [TechTab, string][] = [
  ['query', 'Truy vấn'],
  ['retrieval', 'Truy xuất'],
  ['time', 'Thời gian & chi phí'],
  ['json', 'Thô (JSON)'],
]
const STAGE_LABEL: Record<string, string> = {
  rewrite: 'Hiểu câu hỏi',
  retrieve: 'Tìm tài liệu',
  rerank: 'Xếp hạng',
  generate: 'Soạn câu trả lời',
}

interface Props {
  panel: PanelKind
  tech: boolean
  focus: BotMsg | null
  selSrc: number
  techTab: TechTab
  sheetFull: boolean
  onSelSrc: (n: number) => void
  onPanel: (p: PanelKind) => void
  onTab: (t: TechTab) => void
  onSheet: (full: boolean) => void
}

export function Panel(p: Props) {
  const d = p.focus?.done
  const srcs = d?.citations ?? []
  const body = useRef<HTMLDivElement>(null)
  const dragY = useRef<number | null>(null)
  const skipClick = useRef(false)

  useEffect(() => {
    if (p.panel !== 'sources') return
    const t = window.setTimeout(() => {
      body.current
        ?.querySelector(`[data-src="${p.selSrc}"]`)
        ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }, 200)
    return () => window.clearTimeout(t)
  }, [p.panel, p.selSrc, p.focus?.id])

  const step = (dir: number) => {
    if (!srcs.length) return
    const i = srcs.findIndex((c) => c.n === p.selSrc)
    p.onSelSrc(srcs[(i + dir + srcs.length) % srcs.length].n)
  }

  return (
    <aside className="panel" aria-label="Chi tiết" aria-hidden={!p.panel}>
      <div className="panel__inner">
        <button
          className="sheet-handle"
          aria-label="Kéo để mở rộng hoặc thu nhỏ"
          onPointerDown={(e) => {
            dragY.current = e.clientY
            e.currentTarget.setPointerCapture?.(e.pointerId)
          }}
          onPointerUp={(e) => {
            const dy = e.clientY - (dragY.current ?? e.clientY)
            dragY.current = null
            if (dy < -30) p.onSheet(true)
            else if (dy > 30) {
              if (p.sheetFull) p.onSheet(false)
              else p.onPanel(null)
            } else if (Math.abs(dy) <= 4 && e.pointerType !== 'mouse') p.onSheet(!p.sheetFull)
            skipClick.current = true
          }}
          onClick={() => {
            if (skipClick.current) {
              skipClick.current = false
              return
            }
            p.onSheet(!p.sheetFull)
          }}
        >
          <span className="grab" />
        </button>
        <div className="panel__head">
          {!p.tech && <h2 className="panel__title">Nguồn ({srcs.length})</h2>}
          {p.tech && (
            <div className="seg" role="tablist" aria-label="Chế độ bảng">
              <button role="tab" aria-selected={p.panel === 'sources'} onClick={() => p.onPanel('sources')}>
                Nguồn ({srcs.length})
              </button>
              <button role="tab" aria-selected={p.panel === 'tech'} onClick={() => p.onPanel('tech')}>
                Kỹ thuật
              </button>
            </div>
          )}
          <button className="btn btn--ghost btn--icon" aria-label="Đóng bảng (Esc)" onClick={() => p.onPanel(null)}>
            <Icon name="x" lg />
          </button>
        </div>

        {p.panel === 'sources' && (
          <>
            <div className="panel__body" ref={body}>
              {srcs.length === 0 && (
                <p className="empty-note">Chưa có nguồn nào cho câu trả lời này.</p>
              )}
              {srcs.map((c) => {
                const info = club(c.club)
                const sel = c.n === p.selSrc
                return (
                  <button
                    key={c.n}
                    className={`src-card ${info.cls} ${sel ? 'is-selected' : ''}`}
                    data-src={c.n}
                    aria-current={sel}
                    onClick={() => p.onSelSrc(c.n)}
                  >
                    <span className="src-card__head">
                      <span className="num">{c.n}</span>
                      <span className="badge">{info.label}</span>
                      <span className="src-card__topic">{c.topic}</span>
                      <span className="src-id">#{c.id}</span>
                    </span>
                    <span className="src-card__text">
                      {highlight(c.text, p.focus?.text ?? '').map((h, i) =>
                        h.h ? (
                          <mark className="hl" key={i}>
                            {h.s}
                          </mark>
                        ) : (
                          <span key={i}>{h.s}</span>
                        ),
                      )}
                    </span>
                  </button>
                )
              })}
              {srcs.length > 0 && (
                <p className="fakenote">
                  5 đoạn đưa vào ngữ cảnh khi soạn câu trả lời. Đoạn có số trong câu trả lời là đoạn được trích dẫn; phần
                  tô vàng là số liệu trùng với câu trả lời.
                </p>
              )}
            </div>
            <div className="panel__foot">
              <button className="btn btn--outline btn--sm" onClick={() => step(-1)}>
                <Icon name="chevL" />
                Trước
              </button>
              <span className="mono">{srcs.length ? `Nguồn ${p.selSrc} / ${srcs.length}` : '—'}</span>
              <button className="btn btn--outline btn--sm" onClick={() => step(1)}>
                Sau
                <Icon name="chevR" />
              </button>
            </div>
          </>
        )}

        {p.panel === 'tech' && (
          <>
            <div className="tabs" role="tablist" aria-label="Chế độ kỹ thuật">
              {TABS.map(([k, label]) => (
                <button key={k} className="tab" role="tab" aria-selected={p.techTab === k} onClick={() => p.onTab(k)}>
                  {label}
                </button>
              ))}
            </div>
            <div className="panel__body">
              {!p.focus?.done ? (
                <p className="empty-note">
                  Chưa có phản hồi để phân tích. Hãy đặt một câu hỏi, rồi mở lại tab này.
                </p>
              ) : (
                <TechBody m={p.focus} tab={p.techTab} />
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  )
}

type SortKey = 'id' | 'club' | 'topic' | 'bm25_rank' | 'dense_rank' | 'rerank_rank' | 'status'

function TechBody({ m, tab }: { m: BotMsg; tab: TechTab }) {
  const d = m.done!
  const t = d.trace
  const [sortKey, setSortKey] = useState<SortKey>('rerank_rank')
  const [asc, setAsc] = useState(true)
  const [copied, setCopied] = useState(false)

  const citedIds = useMemo(() => new Set(shownCitations(m).filter((c) => c.cited).map((c) => c.id)), [m])
  const status = (c: Candidate) => (citedIds.has(c.id) ? 2 : c.selected ? 1 : 0)

  if (tab === 'query') {
    const clubs = t.clubs.map((k) => club(k))
    return (
      <div className="tech-body">
        <div>
          <div className="lbl">Câu gốc</div>
          <div className="qbox mono">{t.original_query}</div>
        </div>
        <div>
          <div className="lbl">Sau khi chuẩn hóa (Haiku viết lại: thêm dấu, mở rộng viết tắt)</div>
          <div className="qbox">{t.rewritten_query}</div>
        </div>
        {t.sub_queries.length > 0 && (
          <div>
            <div className="lbl">Câu hỏi con</div>
            {t.sub_queries.map((q) => (
              <div className="qbox" key={q} style={{ marginBottom: 6 }}>
                {q}
              </div>
            ))}
          </div>
        )}
        <div>
          <div className="lbl">Mở rộng viết tắt (BM25)</div>
          {t.expansions.length ? (
            <div className="chips">
              {t.expansions.map((x) => (
                <span className="exp" key={x.from}>
                  <span className="from">{x.from}</span>
                  <Icon name="arrowR" />
                  <span className="to">{x.to}</span>
                </span>
              ))}
            </div>
          ) : (
            <p className="fakenote">Không có từ viết tắt cần mở rộng.</p>
          )}
        </div>
        <div>
          <div className="lbl">CLB suy ra từ câu hỏi (trace.clubs)</div>
          {clubs.length ? (
            <div className="chips">
              {clubs.map((c) => (
                <span className={`badge ${c.cls}`} key={c.key}>
                  {c.label}
                </span>
              ))}
            </div>
          ) : (
            <p className="fakenote">Không suy ra được: tìm trên toàn bộ tài liệu.</p>
          )}
        </div>
      </div>
    )
  }

  if (tab === 'retrieval') {
    const cands = t.candidates
    const nCtx = cands.filter((c) => c.selected).length
    const nCited = d.abstained ? 0 : citedIds.size
    const funnel = [
      { label: `${cands.length} ứng viên`, n: cands.length, w: '100%', cls: '' },
      { label: `${nCtx} được chọn`, n: nCtx, w: `${Math.round((nCtx / cands.length) * 100)}%`, cls: 'funnel__bar--2' },
      {
        label: `${nCited} được trích dẫn`,
        n: nCited,
        w: `${Math.max(Math.round((nCited / cands.length) * 100), 20)}%`,
        cls: 'funnel__bar--3',
      },
    ]
    const nv = (v: number | null) => (v == null ? 99 : v)
    const sorted = [...cands].sort((a, b) => {
      const dir = asc ? 1 : -1
      if (sortKey === 'id') return dir * (a.id - b.id)
      if (sortKey === 'club') return dir * club(a.club).label.localeCompare(club(b.club).label, 'vi')
      if (sortKey === 'topic') return dir * a.topic.localeCompare(b.topic, 'vi')
      if (sortKey === 'status') return dir * (status(b) - status(a))
      return dir * (nv(a[sortKey]) - nv(b[sortKey]))
    })
    const heads: [SortKey, string][] = [
      ['id', '#id'],
      ['club', 'CLB'],
      ['topic', 'Chủ đề'],
      ['bm25_rank', 'Hạng BM25'],
      ['dense_rank', 'Hạng Dense'],
      ['rerank_rank', 'Hạng Rerank'],
      ['status', 'Trạng thái'],
    ]
    const rk = (v: number | null) => (v == null ? '—' : `#${v}`)
    const top = (v: number | null) => (v != null && v <= 5 ? 'is-top' : '')
    return (
      <div className="tech-body">
        <div>
          <div className="lbl">Dòng chảy truy xuất</div>
          <div className="funnel">
            {funnel.map((f) => (
              <div className="funnel__row" key={f.cls}>
                <div className={`funnel__bar ${f.cls}`} style={{ width: f.w }}>
                  {f.label}
                </div>
                <span className="funnel__num">{f.n}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="lbl">Ứng viên ({cands.length}) · cột hiển thị HẠNG (— là không có trong danh sách)</div>
          <div className="ctbl-wrap">
            <table className="ctbl">
              <thead>
                <tr>
                  {heads.map(([k, label]) => {
                    const act = sortKey === k
                    return (
                      <th scope="col" key={k} aria-sort={act ? (asc ? 'ascending' : 'descending') : 'none'}>
                        <button
                          onClick={() => {
                            setAsc(act ? !asc : true)
                            setSortKey(k)
                          }}
                        >
                          {label}
                          {act && <Icon name={asc ? 'sortUp' : 'sortDown'} size={12} />}
                        </button>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {sorted.map((c) => {
                  const s = status(c)
                  const info = club(c.club)
                  return (
                    <tr key={c.id} className={s === 2 ? 'is-selected' : s === 1 ? '' : 'is-dim'}>
                      <td className="mono">#{c.id}</td>
                      <td>
                        <span className={`badge ${info.cls}`}>{info.label}</span>
                      </td>
                      <td className="topic">{c.topic}</td>
                      <td className={`rk ${top(c.bm25_rank)}`}>{rk(c.bm25_rank)}</td>
                      <td className={`rk ${top(c.dense_rank)}`}>{rk(c.dense_rank)}</td>
                      <td className={`rk ${top(c.rerank_rank)}`}>{rk(c.rerank_rank)}</td>
                      <td>
                        <span className={s === 2 ? 'pill-sel' : s === 1 ? 'pill-ctx' : 'pill-mid'}>
                          {s === 2 ? 'Trích dẫn' : s === 1 ? 'Đã chọn' : 'Loại'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  if (tab === 'time') {
    const total = t.stages.reduce((a, s) => a + s.ms, 0) || 1
    let start = 0
    const rows = t.stages.map((s) => {
      const r = { ...s, left: (start / total) * 100, width: (s.ms / total) * 100 }
      start += s.ms
      return r
    })
    return (
      <div className="tech-body">
        <div>
          <div className="lbl">Thời gian theo bước</div>
          <div className="wf">
            {rows.map((w) => (
              <div className="wf__row" key={w.name}>
                <span>{STAGE_LABEL[w.name] ?? w.name}</span>
                <span className="wf__track">
                  <span className="wf__bar" style={{ left: `${w.left.toFixed(2)}%`, width: `${Math.max(w.width, 0.8).toFixed(2)}%` }} />
                </span>
                <span className="wf__ms">{ms(w.ms)}</span>
              </div>
            ))}
            <div className="wf__total">
              <span>Tổng (cả mạng)</span>
              <span className="mono">{ms(d.latency_ms)}</span>
            </div>
          </div>
        </div>
        <div className="metrics">
          <div className="metric">
            <div className="metric__k">Số lời gọi LLM</div>
            <div className="metric__v">{t.llm_calls}</div>
          </div>
          <div className="metric">
            <div className="metric__k">Token vào / ra (≈ ước tính)</div>
            <div className="metric__v">
              ≈ {grp(t.tokens.in)} / {grp(t.tokens.out)}
            </div>
          </div>
          <div className="metric">
            <div className="metric__k">Chi phí (USD, ≈)</div>
            <div className="metric__v">≈ {usd(t.cost_usd)}</div>
          </div>
          <div className="metric">
            <div className="metric__k">Lời gọi trúng cache</div>
            <div className="metric__v">
              {t.llm_cache_hits} / {t.llm_calls}
            </div>
          </div>
        </div>
        {t.incidents.length > 0 && (
          <div>
            <div className="lbl">Sự cố gateway (đã dùng phương án dự phòng)</div>
            {t.incidents.map((x, i) => (
              <div className="qbox mono" key={i} style={{ marginBottom: 6 }}>
                {x.stage}: {x.error}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  const lines = prettyJson(d)
  return (
    <div className="tech-body">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="lbl" style={{ margin: 0 }}>
          Phản hồi thô (sự kiện done)
        </div>
        <button
          className="btn btn--outline btn--sm"
          onClick={() => {
            navigator.clipboard?.writeText(JSON.stringify(d, null, 2)).catch(() => {})
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1600)
          }}
        >
          <Icon name="copy" />
          {copied ? 'Đã sao chép' : 'Sao chép'}
        </button>
      </div>
      <div className="code" tabIndex={0} role="region" aria-label="JSON phản hồi">
        {lines.map((ln, i) => (
          <div className="jl" key={i}>
            {tokenizeJsonLine(ln).map((tk, j) => (
              <span className={tk.cls} key={j}>
                {tk.t}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

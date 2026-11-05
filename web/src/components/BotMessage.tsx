import { useEffect, useState } from 'react'
import { citationAria, club, ms, plainAnswer, sec, segments, usd } from '../lib/format'
import type { BotMsg } from '../lib/model'
import type { Citation } from '../lib/types'
import { Icon, type IconName } from './Icon'

const STEPS: { label: string; icon: IconName }[] = [
  { label: 'Hiểu câu hỏi', icon: 'help' },
  { label: 'Tìm tài liệu', icon: 'search' },
  { label: 'Xếp hạng', icon: 'bars' },
  { label: 'Soạn câu trả lời', icon: 'spark' },
]
const STAGE_LABEL: Record<string, string> = {
  rewrite: 'hiểu câu hỏi',
  retrieve: 'tìm tài liệu',
  dense: 'tìm theo ngữ nghĩa',
  index_dense: 'tìm theo ngữ nghĩa',
  rerank: 'xếp hạng',
  generate: 'soạn câu trả lời',
  generate_stream: 'soạn câu trả lời',
}
const LONG_ANSWER = 700
const FB_REASONS = ['Sai thông tin', 'Thiếu ý', 'Không đúng trọng tâm', 'Khác']

/** Nguồn hiển thị dưới câu trả lời: các đoạn được trích dẫn; nếu model không ghi [n] thì toàn bộ ngữ cảnh. */
export function shownCitations(m: BotMsg): Citation[] {
  const all = m.done?.citations ?? []
  const cited = all.filter((c) => c.cited)
  return cited.length ? cited : all
}

function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!active) return
    const t = window.setInterval(() => setNow(Date.now()), 250)
    return () => window.clearInterval(t)
  }, [active])
  return now
}

function SrcMini({ c, onOpen }: { c: Citation; onOpen: () => void }) {
  const info = club(c.club)
  return (
    <button className={`src-mini ${info.cls}`} onClick={onOpen} aria-label={citationAria(c)}>
      <span className="src-mini__head">
        <span className="num">{c.n}</span>
        <span className="badge">{info.label}</span>
        <span className="src-id">#{c.id}</span>
      </span>
      <span className="src-mini__topic">{c.topic}</span>
      <span className="src-mini__text">{c.text}</span>
    </button>
  )
}

interface Props {
  m: BotMsg
  tech: boolean
  canRetry: boolean
  onOpenSources: (n: number) => void
  onOpenTech: () => void
  onRetry: () => void
  onRephrase: () => void
  onSuggest: () => void
  onVote: (v: 'up' | 'down' | undefined, sent?: boolean) => void
}

export function BotMessage({ m, tech, canRetry, onOpenSources, onOpenTech, onRetry, onRephrase, onSuggest, onVote }: Props) {
  const [open, setOpen] = useState(false)
  const [more, setMore] = useState(false)
  const [copied, setCopied] = useState(false)
  const [fbOpen, setFbOpen] = useState(false)
  const [fbReason, setFbReason] = useState<string | null>(null)
  const [fbNote, setFbNote] = useState('')
  const now = useNow(m.error?.kind === 'retry')

  const d = m.done
  const done = m.status === 'done'
  const running = m.status === 'running'
  const err = m.status === 'error' || m.error?.kind === 'retry'
  const abs = !!d?.abstained
  const cites = shownCitations(m)
  // Reranker trả danh sách rỗng (không có đoạn liên quan) cũng được backend ghi là "fallback", nhưng không phải lỗi gateway.
  const isEmptyRerank = (f: { stage: string | null; error?: string }) =>
    f.stage === 'rerank' && (f.error ?? '').includes('không có id hợp lệ')
  const emptyRerank = m.fallbacks.some(isEmptyRerank)
  const gatewayIssues = m.fallbacks.filter((f) => !isEmptyRerank(f))
  const byN = new Map((d?.citations ?? []).map((c) => [c.n, c]))

  const parts = done
    ? segments(m.text)
    : [{ t: 'text' as const, s: m.text }] // đang stream: [n] là chữ thường, chưa bấm được
  const long = done && m.text.length > LONG_ANSWER
  const clamped = long && !more

  const countdown =
    m.error?.retryUntil !== undefined ? Math.max(0, Math.ceil((m.error.retryUntil - now) / 1000)) : null

  const copy = () => {
    navigator.clipboard?.writeText(plainAnswer(m.text)).catch(() => {})
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="msg">
      {done && (
        <button className="steps-sum" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="ok">✓</span>
          <span className="mono">
            4 bước · {sec(d!.latency_ms)} · {abs ? 'chưa có nguồn khớp' : `${cites.length} nguồn`}
          </span>
          <Icon name="chevD" />
        </button>
      )}
      {(!done || open) && (
        <div className="steps" role="group" aria-label="Tiến trình xử lý">
          {STEPS.map((st, i) => {
            const z = m.steps[i]
            const t = m.stepMs[i]
            return (
              <div className={`step step--${z}`} key={st.label}>
                <div className="step__top">
                  <span className="step__ico">
                    {z === 'running' && <span className="spinner" />}
                    {z === 'done' && <Icon name="check" />}
                    {z === 'error' && <Icon name="x" />}
                    {z === 'pending' && <Icon name={st.icon} />}
                  </span>
                  <span className="step__label">{st.label}</span>
                </div>
                <span className="step__time">
                  {t != null ? ms(t) : z === 'running' ? '…' : z === 'error' ? 'lỗi' : ''}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {err && m.error && (
        <div className="errcard" role="alert">
          <span className="errcard__ico">
            <Icon name="alert" lg />
          </span>
          <div className="errcard__text">
            {m.error.text}
            <div className="errcard__sub">
              {m.error.kind === 'retry' && countdown !== null
                ? `${m.error.sub.replace(/\.$/, '')} sau ${countdown} giây.`
                : m.error.sub}
            </div>
          </div>
          {m.error.kind !== 'retry' && (
            <button className="btn btn--outline btn--sm" onClick={onRetry} disabled={!canRetry}>
              <Icon name="refresh" />
              Thử lại
            </button>
          )}
        </div>
      )}

      {!abs && m.text && (
        <div className={`answer ${clamped ? 'is-clamped' : ''}`}>
          {parts.map((p, i) => {
            if (p.t === 'text') return <span key={i}>{p.s}</span>
            const c = byN.get(p.n)
            if (!c) return null
            const info = club(c.club)
            return (
              <button key={i} className={`cite ${info.cls}`} aria-label={citationAria(c)} onClick={() => onOpenSources(c.n)}>
                {c.n}
                <span className="cite-tip" role="tooltip">
                  {c.text.length > 220 ? `${c.text.slice(0, 220)}…` : c.text}
                </span>
              </button>
            )
          })}
          {running && m.steps[3] === 'running' && <span className="caret" aria-hidden="true" />}
        </div>
      )}
      {long && (
        <button className="more-btn" onClick={() => setMore(!more)}>
          {clamped ? 'Xem thêm' : 'Thu gọn'}
        </button>
      )}

      {done && abs && (
        <div className="abstain" role="note">
          <div className="abstain__head">
            <Icon name="info" lg />
            Tài liệu chưa có thông tin này
          </div>
          <p>{plainAnswer(m.text) || `Tài liệu hiện có không đề cập đến “${m.query}”.`}</p>
          {(d?.citations.length ?? 0) > 0 && (
            <div>
              <div className="abstain__label">Thông tin gần nhất có thể hữu ích</div>
              <div className="strip">
                {d!.citations.slice(0, 2).map((c) => (
                  <SrcMini key={c.n} c={c} onOpen={() => onOpenSources(c.n)} />
                ))}
              </div>
            </div>
          )}
          <div className="abstain__actions">
            <button className="btn btn--outline btn--sm" onClick={onRephrase}>
              <Icon name="pencil" />
              Hỏi lại theo cách khác
            </button>
            <button className="btn btn--outline btn--sm" onClick={onSuggest}>
              Xem các câu gợi ý
            </button>
          </div>
        </div>
      )}

      {m.status === 'stopped' && <span className="stopped-label">Đã dừng</span>}

      {done && !abs && cites.length > 0 && (
        <div className="strip" aria-label="Nguồn">
          {cites.slice(0, 3).map((c) => (
            <SrcMini key={c.n} c={c} onOpen={() => onOpenSources(c.n)} />
          ))}
          {cites.length > 3 && (
            <button className="src-more" onClick={() => onOpenSources(cites[3].n)}>
              +{cites.length - 3} nguồn
            </button>
          )}
        </div>
      )}

      {done && gatewayIssues.length > 0 && (
        <p className="fakenote" role="note">
          ⚠ Gateway gặp sự cố ở bước {[...new Set(gatewayIssues.map((f) => STAGE_LABEL[f.stage ?? ''] ?? f.stage))].join(', ')}
          ; hệ thống đã dùng phương án dự phòng nên câu trả lời có thể kém chính xác hơn.
        </p>
      )}
      {done && tech && emptyRerank && (
        <p className="fakenote" role="note">
          Bước xếp hạng không chọn đoạn nào (thường gặp với câu ngoài tài liệu): giữ thứ hạng tìm kiếm.
        </p>
      )}

      {done && (
        <div className={`actions ${fbOpen ? 'is-on' : ''}`} role="group" aria-label="Hành động với câu trả lời">
          {!abs && (
            <>
              <button className="act" onClick={copy}>
                <Icon name="copy" />
                {copied ? 'Đã sao chép' : 'Sao chép'}
              </button>
              <button
                className={`act ${m.vote === 'up' ? 'is-on' : ''}`}
                aria-pressed={m.vote === 'up'}
                aria-label="Câu trả lời hữu ích"
                onClick={() => {
                  setFbOpen(false)
                  onVote(m.vote === 'up' ? undefined : 'up')
                }}
              >
                <Icon name="up" />
              </button>
              <button
                className={`act ${m.vote === 'down' ? 'is-on' : ''}`}
                aria-pressed={m.vote === 'down'}
                aria-label="Câu trả lời chưa tốt"
                onClick={() => {
                  onVote('down')
                  setFbReason(null)
                  setFbNote('')
                  setFbOpen(true)
                }}
              >
                <Icon name="down" />
              </button>
              {m.feedbackSent && <span className="fakenote">Cảm ơn phản hồi của bạn.</span>}
              <span className="act-sep" />
              <button className="act" onClick={() => onOpenSources(cites[0]?.n ?? 1)}>
                <Icon name="book" />
                Xem nguồn
              </button>
            </>
          )}
          <button className="act" onClick={onOpenTech}>
            <Icon name="flow" />
            Xem cách hệ thống trả lời
          </button>
        </div>
      )}

      {fbOpen && (
        <div className="popover fb" role="dialog" aria-label="Lý do chưa hài lòng" style={{ top: '100%', left: 0 }}>
          <div className="fb__title">Điều gì chưa ổn?</div>
          <div className="fb__reasons">
            {FB_REASONS.map((r) => (
              <button
                key={r}
                className={`chip ${fbReason === r ? 'is-active' : ''}`}
                aria-pressed={fbReason === r}
                onClick={() => setFbReason(r)}
              >
                {r}
              </button>
            ))}
          </div>
          <textarea
            className="fb__note"
            placeholder="Ghi chú thêm (không bắt buộc)"
            aria-label="Ghi chú"
            value={fbNote}
            onChange={(e) => setFbNote(e.target.value)}
          />
          <div className="fb__row">
            <button className="btn btn--ghost btn--sm" onClick={() => setFbOpen(false)}>
              Hủy
            </button>
            <button
              className="btn btn--primary btn--sm"
              onClick={() => {
                setFbOpen(false)
                onVote('down', true)
              }}
            >
              Gửi
            </button>
          </div>
        </div>
      )}

      {tech && done && d && (
        <span className="techline">
          {ms(d.latency_ms)} · {d.trace.llm_calls} lời gọi LLM
          {d.trace.llm_cache_hits ? ` (${d.trace.llm_cache_hits} từ cache)` : ''} · ≈{usd(d.trace.cost_usd)}
        </span>
      )}
    </div>
  )
}

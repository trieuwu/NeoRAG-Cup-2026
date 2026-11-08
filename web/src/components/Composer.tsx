import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { MAX_CHARS } from '../lib/useChat'
import { Icon } from './Icon'

interface Props {
  value: string
  running: boolean
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
}

export interface ComposerHandle {
  focus: () => void
}

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { value, running, onChange, onSend, onStop },
  ref,
) {
  const ta = useRef<HTMLTextAreaElement>(null)
  useImperativeHandle(ref, () => ({ focus: () => ta.current?.focus() }), [])

  // tự giãn chiều cao (tối đa 144px), kể cả khi giá trị đổi từ bên ngoài (Hỏi lại theo cách khác)
  useEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 144)}px`
  }, [value])

  const len = value.length
  const over = len > MAX_CHARS
  const blank = !value.trim() // chuỗi toàn khoảng trắng coi như rỗng
  const cls = over ? 'is-error' : running ? 'is-sending' : ''

  return (
    <div className="composer-wrap">
      <div className="inner">
        <div className={`composer ${cls}`}>
          <label className="sr-only" htmlFor="s2b-ta">
            Câu hỏi
          </label>
          <textarea
            id="s2b-ta"
            ref={ta}
            className="composer__ta"
            rows={1}
            placeholder="Nhập câu hỏi… (có thể gõ không dấu)"
            value={value}
            aria-invalid={over}
            aria-describedby={over ? 's2b-ta-err' : 's2b-ta-hint'}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                if (!running && !blank && !over) onSend()
              }
            }}
          />
          <div className="composer__row">
            <span className="grow" style={{ flex: 1 }} />
            {len > 400 && (
              <span className={`composer__count mono ${over ? 'is-over' : ''}`}>
                {len} / {MAX_CHARS}
              </span>
            )}
            {running ? (
              <button className="btn btn--stop" onClick={onStop}>
                <Icon name="stop" fill />
                Dừng
              </button>
            ) : (
              <button className="send" aria-label="Gửi câu hỏi" disabled={blank || over} onClick={onSend}>
                <Icon name="send" lg />
              </button>
            )}
          </div>
        </div>
        {over && (
          <p className="field-err" role="alert" id="s2b-ta-err">
            <Icon name="alertCircle" />
            Câu hỏi tối đa 500 ký tự. Hãy rút gọn trước khi gửi.
          </p>
        )}
        <p className="hint" id="s2b-ta-hint">
          Enter để gửi · Shift + Enter xuống dòng · / để nhập câu hỏi
        </p>
      </div>
    </div>
  )
})

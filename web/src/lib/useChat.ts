import { useCallback, useEffect, useRef, useState } from 'react'
import { type BotMsg, type Conv, loadConvs, newBot, saveConvs, uid } from './model'
import { HttpError, streamChat } from './sse'
import { STAGES, type ServerEvent } from './types'

export const MAX_CHARS = 500
const WATCHDOG_MS = 90_000 // không có sự kiện nào (kể cả ping) trong 90 giây → hết thời gian chờ
const MIN_STAGE_MS = 250 // câu trúng cache xong trong ~170 ms: giữ mỗi bước ít nhất 250 ms để người xem kịp thấy
const TOKEN_GAP_MS = 14 // token dồn dập (câu trả lời lấy từ cache) → hiện dần như đang gõ

export type Demo = 'retry' | 'timeout'

const sleep = (t: number) => new Promise((r) => setTimeout(r, t))
const reducedMotion = () =>
  typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

interface Run {
  botId: string
  ctrl: AbortController
  lastEvent: number
  watchdog: number
}

export function useChat() {
  const [convs, setConvs] = useState<Conv[]>(loadConvs)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && !navigator.onLine)
  const run = useRef<Run | null>(null)

  useEffect(() => saveConvs(convs), [convs])
  useEffect(() => {
    const on = () => setOffline(false)
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])

  const patchBot = useCallback((id: string, fn: (b: BotMsg) => BotMsg) => {
    setConvs((cs) =>
      cs.map((c) =>
        c.msgs.some((m) => m.id === id)
          ? { ...c, msgs: c.msgs.map((m) => (m.id === id && m.role === 'bot' ? fn(m) : m)) }
          : c,
      ),
    )
  }, [])

  const finishRun = useCallback(() => {
    if (run.current) window.clearInterval(run.current.watchdog)
    run.current = null
  }, [])

  /** Chạy một câu hỏi vào bot message `botId` (đã có sẵn trong hội thoại). */
  const execute = useCallback(
    (botId: string, query: string, demo?: Demo) => {
      const ctrl = new AbortController()
      const r: Run = { botId, ctrl, lastEvent: Date.now(), watchdog: 0 }
      run.current = r
      const limit = demo === 'timeout' ? 4_000 : WATCHDOG_MS
      r.watchdog = window.setInterval(() => {
        if (Date.now() - r.lastEvent < limit) return
        ctrl.abort('timeout')
        finishRun()
        patchBot(botId, (b) => ({
          ...b,
          status: 'error',
          steps: b.steps.map((s) => (s === 'running' ? 'error' : s)),
          error: {
            kind: 'timeout',
            text: 'Câu trả lời mất quá nhiều thời gian.',
            sub: `Không nhận được phản hồi nào sau ${Math.round(limit / 1000)} giây. Bạn có thể thử lại.`,
          },
        }))
      }, 1000)

      const shownAt: Partial<Record<string, number>> = {}
      let chain = Promise.resolve()
      let lastToken = 0
      const live = () => run.current === r && !ctrl.signal.aborted

      const apply = async (ev: ServerEvent) => {
        if (!live()) return
        if (ev.event === 'stage') {
          const i = STAGES.indexOf(ev.data.name)
          if (i < 0) return
          if (ev.data.status === 'start') {
            shownAt[ev.data.name] = Date.now()
            patchBot(botId, (b) => {
              const steps = [...b.steps]
              steps[i] = 'running'
              return { ...b, steps, error: b.error?.kind === 'retry' ? undefined : b.error }
            })
          } else {
            const wait = (shownAt[ev.data.name] ?? 0) + MIN_STAGE_MS - Date.now()
            if (wait > 0 && !reducedMotion()) await sleep(wait)
            patchBot(botId, (b) => {
              const steps = [...b.steps]
              const stepMs = [...b.stepMs]
              steps[i] = 'done'
              stepMs[i] = ev.data.ms ?? null
              if (i < 3 && steps[i + 1] === 'pending') steps[i + 1] = 'running'
              return { ...b, steps, stepMs, error: b.error?.kind === 'retry' ? undefined : b.error }
            })
          }
        } else if (ev.event === 'token') {
          const now = Date.now()
          if (now - lastToken < TOKEN_GAP_MS && !reducedMotion()) await sleep(TOKEN_GAP_MS)
          lastToken = Date.now()
          patchBot(botId, (b) => ({
            ...b,
            text: b.text + ev.data.text,
            error: b.error?.kind === 'retry' ? undefined : b.error,
          }))
        } else if (ev.event === 'incident') {
          const d = ev.data
          if (d.type === 'retry') {
            const i = STAGES.indexOf(d.stage as (typeof STAGES)[number])
            patchBot(botId, (b) => {
              const steps = [...b.steps]
              if (i >= 0) steps[i] = 'error'
              return {
                ...b,
                steps,
                error: {
                  kind: 'retry',
                  text: 'Hệ thống đang quá tải, thử lại sau ít giây.',
                  sub: `Hệ thống tự thử lại${d.attempt ? ` (lần ${d.attempt})` : ''}.`,
                  retryUntil: Date.now() + (d.wait_s ?? 5) * 1000,
                },
              }
            })
          } else {
            patchBot(botId, (b) => ({ ...b, fallbacks: [...b.fallbacks, d] }))
          }
        } else if (ev.event === 'done') {
          finishRun()
          patchBot(botId, (b) => ({
            ...b,
            status: 'done',
            steps: b.steps.map(() => 'done'),
            stepMs: ['rewrite', 'retrieve', 'rerank', 'generate'].map(
              (n, i) => ev.data.trace.stages.find((s) => s.name === n)?.ms ?? b.stepMs[i],
            ),
            text: ev.data.answer,
            done: ev.data,
            error: undefined,
          }))
        } else if (ev.event === 'error') {
          finishRun()
          patchBot(botId, (b) => ({
            ...b,
            status: 'error',
            steps: b.steps.map((s) => (s === 'running' ? 'error' : s)),
            error: { kind: 'error', text: 'Đã có lỗi khi tạo câu trả lời.', sub: ev.data.message },
          }))
        }
      }

      const onEvent = (ev: ServerEvent) => {
        r.lastEvent = Date.now() // mọi sự kiện, kể cả ping, đặt lại đồng hồ chờ
        if (ev.event === 'ping') return
        chain = chain.then(() => apply(ev))
      }

      const start = async () => {
        if (demo === 'retry') {
          // Mô phỏng: chèn một lần "gateway quá tải" ở phía client rồi chạy câu hỏi thật.
          onEvent({ event: 'stage', data: { name: 'rewrite', status: 'start' } })
          await sleep(400)
          onEvent({
            event: 'incident',
            data: { type: 'retry', stage: 'rewrite', attempt: 1, wait_s: 5 },
          })
          await sleep(5000)
        }
        if (demo === 'timeout') {
          onEvent({ event: 'stage', data: { name: 'rewrite', status: 'start' } })
          return new Promise<void>(() => {}) // không bao giờ trả lời: đồng hồ chờ sẽ báo lỗi
        }
        await streamChat(query, onEvent, ctrl.signal)
      }

      start()
        .then(() => chain)
        .then(() => {
          // luồng đóng mà không có done/error (vd. server khởi động lại)
          if (live()) {
            finishRun()
            patchBot(botId, (b) =>
              b.status === 'running'
                ? {
                    ...b,
                    status: 'error',
                    steps: b.steps.map((s) => (s === 'running' ? 'error' : s)),
                    error: { kind: 'error', text: 'Kết nối bị đóng giữa chừng.', sub: 'Bạn có thể thử lại.' },
                  }
                : b,
            )
          }
        })
        .catch((err: unknown) => {
          if (ctrl.signal.aborted || run.current !== r) return
          finishRun()
          const http = err instanceof HttpError
          if (!http) setOffline(!navigator.onLine)
          patchBot(botId, (b) => ({
            ...b,
            status: 'error',
            steps: b.steps.map((s) => (s === 'running' ? 'error' : s)),
            error: http
              ? {
                  kind: 'http',
                  text: err.status === 422 ? 'Câu hỏi không hợp lệ.' : `Máy chủ trả lỗi ${err.status}.`,
                  sub: err.status === 422 ? 'Câu hỏi cần từ 1 đến 500 ký tự.' : err.message,
                }
              : {
                  kind: 'offline',
                  text: 'Không kết nối được tới máy chủ.',
                  sub: 'Kiểm tra mạng hoặc máy chủ API (uvicorn app.api:app) rồi thử lại.',
                },
          }))
        })
    },
    [finishRun, patchBot],
  )

  const stop = useCallback(() => {
    const r = run.current
    if (!r) return
    r.ctrl.abort('stopped')
    finishRun()
    patchBot(r.botId, (b) => ({
      ...b,
      status: 'stopped',
      steps: b.steps.map((s) => (s === 'running' ? 'pending' : s)),
      error: undefined,
    }))
  }, [finishRun, patchBot])

  const send = useCallback(
    (raw: string, demo?: Demo) => {
      const text = raw.trim()
      if (!text || text.length > MAX_CHARS || run.current) return false
      const botId = uid('b')
      const user = { id: uid('u'), role: 'user' as const, text }
      const bot = newBot(botId, text)
      const existing = activeId !== null && convs.some((c) => c.id === activeId)
      const convId = existing ? (activeId as string) : uid('c')
      setConvs((cs) =>
        existing
          ? cs.map((c) => (c.id === convId ? { ...c, msgs: [...c.msgs, user, bot] } : c))
          : [{ id: convId, title: text, createdAt: Date.now(), msgs: [user, bot] }, ...cs],
      )
      setActiveId(convId)
      execute(botId, text, demo)
      return true
    },
    [activeId, convs, execute],
  )

  const retry = useCallback(
    (botId: string) => {
      if (run.current) return
      const bot = convs.flatMap((c) => c.msgs).find((m) => m.id === botId)
      if (!bot || bot.role !== 'bot') return
      patchBot(botId, (b) => newBot(b.id, b.query))
      execute(botId, bot.query)
    },
    [convs, execute, patchBot],
  )

  const newChat = useCallback(() => {
    stop()
    setActiveId(null)
  }, [stop])

  const select = useCallback(
    (id: string) => {
      stop()
      setActiveId(id)
    },
    [stop],
  )

  const rename = useCallback((id: string, title: string) => {
    setConvs((cs) => cs.map((c) => (c.id === id && title.trim() ? { ...c, title: title.trim() } : c)))
  }, [])

  const remove = useCallback(
    (id: string) => {
      if (activeId === id) {
        stop()
        setActiveId(null)
      }
      setConvs((cs) => cs.filter((c) => c.id !== id))
    },
    [activeId, stop],
  )

  const active = convs.find((c) => c.id === activeId) ?? null
  const running = !!active?.msgs.some((m) => m.role === 'bot' && m.status === 'running')

  return {
    convs,
    active,
    running,
    offline,
    setOffline,
    send,
    stop,
    retry,
    newChat,
    select,
    rename,
    remove,
    patchBot,
  }
}

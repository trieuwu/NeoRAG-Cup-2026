import type { DonePayload, IncidentEvent } from './types'

export type StepState = 'pending' | 'running' | 'done' | 'error'

export interface BotError {
  kind: 'retry' | 'timeout' | 'error' | 'offline' | 'http'
  text: string
  sub: string
  retryUntil?: number // incident retry: thời điểm backend thử lại (ms epoch)
}

export interface UserMsg {
  id: string
  role: 'user'
  text: string
}

export interface BotMsg {
  id: string
  role: 'bot'
  query: string
  status: 'running' | 'done' | 'error' | 'stopped'
  steps: StepState[]
  stepMs: (number | null)[]
  text: string // phần đã stream (chuỗi thô, [n] là chữ thường)
  done?: DonePayload
  error?: BotError
  fallbacks: IncidentEvent[]
  vote?: 'up' | 'down'
  feedbackSent?: boolean
}

export type Msg = UserMsg | BotMsg

export interface Conv {
  id: string
  title: string
  createdAt: number
  msgs: Msg[]
}

export const newBot = (id: string, query: string): BotMsg => ({
  id,
  role: 'bot',
  query,
  status: 'running',
  steps: ['running', 'pending', 'pending', 'pending'],
  stepMs: [null, null, null, null],
  text: '',
  fallbacks: [],
})

let counter = 0
export const uid = (p: string) => `${p}${Date.now().toString(36)}${(counter++).toString(36)}`

// ---------------------------------------------------------------- lịch sử (chỉ phía client)

const KEY = 's2b.history.v1'

export function loadConvs(): Conv[] {
  try {
    const raw = localStorage.getItem(KEY)
    const convs: Conv[] = raw ? JSON.parse(raw) : []
    // câu đang chạy khi đóng trang → coi như đã dừng
    return convs.map((c) => ({
      ...c,
      msgs: c.msgs.map((m) =>
        m.role === 'bot' && m.status === 'running'
          ? { ...m, status: 'stopped', steps: m.steps.map((s) => (s === 'running' ? 'pending' : s)) }
          : m,
      ),
    }))
  } catch {
    return []
  }
}

export function saveConvs(convs: Conv[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(convs.slice(0, 100)))
  } catch {
    /* hết dung lượng hoặc chế độ riêng tư: bỏ qua */
  }
}

export function groupConvs(convs: Conv[], now = Date.now()) {
  const day = new Date(now)
  day.setHours(0, 0, 0, 0)
  const today = day.getTime()
  const week = today - 6 * 86_400_000
  const groups = [
    { label: 'Hôm nay', items: convs.filter((c) => c.createdAt >= today) },
    { label: '7 ngày qua', items: convs.filter((c) => c.createdAt < today && c.createdAt >= week) },
    { label: 'Cũ hơn', items: convs.filter((c) => c.createdAt < week) },
  ]
  return groups.filter((g) => g.items.length)
}

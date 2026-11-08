import type { ServerEvent } from './types'

/** Bộ phân tích SSE tăng dần: nhận từng mảnh văn bản (có thể cắt giữa dòng/sự kiện), trả về các sự kiện đủ. */
export class SseParser {
  private buf = ''

  push(chunk: string): ServerEvent[] {
    this.buf += chunk.replace(/\r\n/g, '\n')
    const out: ServerEvent[] = []
    let sep: number
    while ((sep = this.buf.indexOf('\n\n')) >= 0) {
      const block = this.buf.slice(0, sep)
      this.buf = this.buf.slice(sep + 2)
      const ev = parseBlock(block)
      if (ev) out.push(ev)
    }
    return out
  }
}

function parseBlock(block: string): ServerEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const i = line.indexOf(':')
    const field = i < 0 ? line : line.slice(0, i)
    const value = i < 0 ? '' : line.slice(i + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  if (!data.length) return null
  try {
    return { event, data: JSON.parse(data.join('\n')) } as ServerEvent
  } catch {
    return null
  }
}

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

/** POST /api/chat và đọc luồng SSE bằng fetch + ReadableStream (không dùng EventSource vì là POST). */
export async function streamChat(
  message: string,
  onEvent: (ev: ServerEvent) => void,
  signal: AbortSignal,
  cite = true,
): Promise<void> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ message, cite }),
    signal,
  })
  if (!res.ok || !res.body) {
    let detail = res.statusText
    try {
      detail = JSON.stringify((await res.json()).detail ?? detail)
    } catch {
      /* body không phải JSON */
    }
    throw new HttpError(res.status, detail)
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  const parser = new SseParser()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    for (const ev of parser.push(value)) onEvent(ev)
  }
}

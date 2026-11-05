import { describe, expect, it } from 'vitest'
import { club, highlight, plainAnswer, prettyJson, segments } from './format'
import { SseParser } from './sse'

describe('SseParser', () => {
  it('ghép sự kiện bị cắt giữa chừng và bỏ qua dòng chú thích', () => {
    const p = new SseParser()
    expect(p.push('event: stage\ndata: {"name":"rewr')).toEqual([])
    const evs = p.push('ite","status":"start"}\n\n: comment\n\nevent: token\r\ndata: {"text":"CLB "}\r\n\r\n')
    expect(evs).toEqual([
      { event: 'stage', data: { name: 'rewrite', status: 'start' } },
      { event: 'token', data: { text: 'CLB ' } },
    ])
  })
  it('đọc ping và bỏ qua data không phải JSON', () => {
    const p = new SseParser()
    expect(p.push('event: ping\ndata: {}\n\nevent: x\ndata: {hỏng\n\n')).toEqual([{ event: 'ping', data: {} }])
  })
})

describe('format', () => {
  it('tách trích dẫn [n], kể cả [1][3] liền nhau', () => {
    expect(segments('Ngày 09/10/2011 [1][3].')).toEqual([
      { t: 'text', s: 'Ngày 09/10/2011 ' },
      { t: 'cite', n: 1 },
      { t: 'cite', n: 3 },
      { t: 'text', s: '.' },
    ])
    expect(plainAnswer('A [1]. B [2][3].')).toBe('A. B.')
  })
  it('ánh xạ tên CLB của corpus và khóa của bước viết lại', () => {
    expect(club('CLB Lập Trình PTIT').label).toBe('ProPTIT')
    expect(club('CLB Multimedia PTIT').cls).toBe('club--mm')
    expect(club('CLB Nhà Sáng Tạo Game PTIT (GCC)').label).toBe('GCC')
    expect(club('proptit').key).toBe('pro')
    expect(club('Cộng đồng S2B').key).toBe('s2b')
  })
  it('tô số liệu trùng với câu trả lời', () => {
    const parts = highlight('Thành lập ngày 09/10/2011 tại PTIT.', 'CLB thành lập ngày 09/10/2011 [1].')
    expect(parts.filter((p) => p.h).map((p) => p.s)).toEqual(['09/10/2011'])
  })
  it('JSON gọn: mỗi object trong mảng một dòng', () => {
    expect(prettyJson({ a: [{ x: 1 }, { x: 2 }] })).toEqual(['{', '  "a": [', '    {"x":1},', '    {"x":2}', '  ]', '}'])
  })
})

import { useState } from 'react'

type Filter = 'all' | 'pro' | 'mm' | 'gcc'

interface Suggest {
  q: string
  badge: string
  cls: string
  clubs: Filter[]
  base?: boolean // hiện khi chọn "Tất cả"
}

// Câu hỏi gợi ý viết riêng cho giao diện (không lấy từ đề Public/Private). Chip CLB chỉ lọc danh sách này,
// không gửi kèm khi hỏi: pipeline tự suy ra CLB từ câu hỏi.
const SUGGEST: Suggest[] = [
  { q: 'CLB Lập Trình PTIT thành lập khi nào, phương châm là gì?', badge: 'ProPTIT', cls: 'club--pro', clubs: ['pro'], base: true },
  { q: 'Muốn vào CLB Multimedia PTIT thì cần làm gì?', badge: 'Multimedia', cls: 'club--mm', clubs: ['mm'], base: true },
  { q: 'GCC có những hoạt động gì cho thành viên?', badge: 'GCC', cls: 'club--gcc', clubs: ['gcc'], base: true },
  { q: 'ProPTIT và GCC, CLB nào thành lập trước?', badge: 'So sánh', cls: 'club--cmp', clubs: ['pro', 'gcc'], base: true },
  { q: 'sv nganh dpt nen vao clb nao o hv', badge: 'Không dấu', cls: 'club--nodau', clubs: ['mm'], base: true },
  { q: 'S2B gồm những câu lạc bộ nào?', badge: 'S2B', cls: 'club--s2b', clubs: [], base: true },
  { q: 'ProPTIT có những hoạt động đào tạo nào cho thành viên mới?', badge: 'ProPTIT', cls: 'club--pro', clubs: ['pro'] },
  { q: 'Thành viên ProPTIT có những nghĩa vụ gì?', badge: 'ProPTIT', cls: 'club--pro', clubs: ['pro'] },
  { q: 'CLB Multimedia PTIT hoạt động trong những lĩnh vực nào?', badge: 'Multimedia', cls: 'club--mm', clubs: ['mm'] },
  { q: 'CLB Multimedia PTIT thành lập năm nào?', badge: 'Multimedia', cls: 'club--mm', clubs: ['mm'] },
  { q: 'CLB Nhà Sáng Tạo Game PTIT ra đời khi nào?', badge: 'GCC', cls: 'club--gcc', clubs: ['gcc'] },
  { q: 'Muốn vào GCC thì cần đáp ứng điều kiện gì?', badge: 'GCC', cls: 'club--gcc', clubs: ['gcc'] },
]

const CHIPS: { label: string; val: Filter; cls: string }[] = [
  { label: 'Tất cả', val: 'all', cls: '' },
  { label: 'ProPTIT', val: 'pro', cls: 'club--pro' },
  { label: 'Multimedia', val: 'mm', cls: 'club--mm' },
  { label: 'GCC', val: 'gcc', cls: 'club--gcc' },
]

export function Hero({ onAsk }: { onAsk: (q: string) => void }) {
  const [filter, setFilter] = useState<Filter>('all')
  const list = SUGGEST.filter((s) => (filter === 'all' ? s.base : s.clubs.includes(filter))).slice(0, 6)
  return (
    <section className="hero">
      <h1>Hỏi gì về S2B cũng được.</h1>
      <p>Câu trả lời dựa trên tài liệu chính thức của ProPTIT, Multimedia và GCC, kèm nguồn để bạn kiểm chứng.</p>
      <div className="chips" role="group" aria-label="Lọc câu hỏi gợi ý theo câu lạc bộ">
        {CHIPS.map((c) => {
          const active = filter === c.val
          return (
            <button
              key={c.val}
              className={`chip ${c.cls} ${active ? 'is-active' : ''}`}
              aria-pressed={active}
              onClick={() => setFilter(c.val)}
            >
              {c.val !== 'all' && <span className="dot" />}
              {c.label}
            </button>
          )
        })}
      </div>
      <div className="suggest-grid">
        {list.map((s) => (
          <button key={s.q} className={`suggest ${s.cls}`} onClick={() => onAsk(s.q)}>
            <span className="badge">{s.badge}</span>
            <span className="suggest__q">{s.q}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

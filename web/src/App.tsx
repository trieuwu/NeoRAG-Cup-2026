import { useCallback, useEffect, useRef, useState } from 'react'
import { BotMessage } from './components/BotMessage'
import { Composer, type ComposerHandle } from './components/Composer'
import { Hero } from './components/Hero'
import { Icon } from './components/Icon'
import { Panel, type PanelKind, type TechTab } from './components/Panel'
import { Sidebar } from './components/Sidebar'
import type { BotMsg } from './lib/model'
import { useChat } from './lib/useChat'

const PREF_KEY = 's2b.prefs.v1'
interface Prefs {
  theme: 'light' | 'dark'
  tech: boolean
  collapsed: boolean
}

function loadPrefs(): Prefs {
  const dark = typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches
  const base: Prefs = { theme: dark ? 'dark' : 'light', tech: false, collapsed: false }
  try {
    return { ...base, ...JSON.parse(localStorage.getItem(PREF_KEY) ?? '{}') }
  } catch {
    return base
  }
}

const ABSTAIN_Q = 'Phí thành viên hằng năm của CLB Multimedia PTIT là bao nhiêu?'
const LONG_Q = 'Giới thiệu chi tiết các hoạt động, đào tạo và sự kiện của CLB Lập Trình PTIT'

export default function App() {
  const chat = useChat()
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs)
  const [drawer, setDrawer] = useState(false)
  const [panel, setPanel] = useState<PanelKind>(null)
  const [sheetFull, setSheetFull] = useState(false)
  const [techTab, setTechTab] = useState<TechTab>('query')
  const [focusId, setFocusId] = useState<string | null>(null)
  const [selSrc, setSelSrc] = useState(1)
  const [input, setInput] = useState('')
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [demoOffline, setDemoOffline] = useState(false)
  const [apiDown, setApiDown] = useState(false)
  const composer = useRef<ComposerHandle>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    try {
      localStorage.setItem(PREF_KEY, JSON.stringify(prefs))
    } catch {
      /* bỏ qua */
    }
  }, [prefs])

  // làm nóng pipeline (nạp index) một lần lúc mở trang
  useEffect(() => {
    fetch('/api/health')
      .then((r) => setApiDown(!r.ok))
      .catch(() => setApiDown(true))
  }, [])

  const msgs = chat.active?.msgs ?? []
  const bots = msgs.filter((m): m is BotMsg => m.role === 'bot')
  const focus = bots.find((m) => m.id === focusId) ?? bots[bots.length - 1] ?? null

  // cuộn xuống cuối khi có nội dung mới
  const lastText = bots[bots.length - 1]?.text.length ?? 0
  const lastStatus = bots[bots.length - 1]?.status
  useEffect(() => {
    const el = scroller.current
    if (el) el.scrollTop = el.scrollHeight
  }, [msgs.length, lastText, lastStatus])

  const send = useCallback(
    (text: string, demo?: 'retry' | 'timeout') => {
      if (chat.send(text, demo)) {
        setInput('')
        setFocusId(null)
        setSelSrc(1)
        setDrawer(false)
      }
    },
    [chat],
  )

  const newChat = useCallback(() => {
    chat.newChat()
    setFocusId(null)
    setDrawer(false)
    setInput('')
    window.setTimeout(() => composer.current?.focus(), 40)
  }, [chat])

  const toggleTech = useCallback(() => {
    setPrefs((p) => ({ ...p, tech: !p.tech }))
    setPanel((cur) => (prefs.tech ? (cur === 'tech' ? null : cur) : 'tech'))
    setSheetFull(false)
  }, [prefs.tech])

  const openSources = (m: BotMsg, n: number) => {
    setFocusId(m.id)
    setSelSrc(n)
    setPanel('sources')
    setSheetFull(false)
    setDrawer(false)
  }

  const closeTop = useCallback(() => {
    if (deleteId) setDeleteId(null)
    else if (panel) setPanel(null)
    else if (drawer) setDrawer(false)
  }, [deleteId, panel, drawer])

  // phím tắt toàn cục
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase() ?? ''
      const typing = tag === 'textarea' || tag === 'input'
      const mod = e.ctrlKey || e.metaKey
      if (mod && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        newChat()
      } else if (mod && e.key === '.') {
        e.preventDefault()
        toggleTech()
      } else if (e.key === 'Escape') {
        closeTop()
      } else if (!typing && e.key === '/') {
        e.preventDefault()
        composer.current?.focus()
      } else if (!typing && panel === 'sources' && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        const srcs = focus?.done?.citations ?? []
        if (!srcs.length) return
        e.preventDefault()
        const i = srcs.findIndex((c) => c.n === selSrc)
        const next = srcs[(i + (e.key === 'ArrowDown' ? 1 : -1) + srcs.length) % srcs.length]
        setSelSrc(next.n)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [newChat, toggleTech, closeTop, panel, focus, selSrc])

  const demo = (kind: string) => {
    setDrawer(false)
    if (kind === 'abstain') send(ABSTAIN_Q)
    else if (kind === 'long') send(LONG_Q)
    else if (kind === 'retry') send('CLB Lập Trình PTIT thành lập khi nào, phương châm là gì?', 'retry')
    else if (kind === 'timeout') send('CLB Lập Trình PTIT thành lập khi nào, phương châm là gì?', 'timeout')
    else if (kind === 'offline') {
      setDemoOffline(true)
      window.setTimeout(() => setDemoOffline(false), 6000)
    }
  }

  const delConv = chat.convs.find((c) => c.id === deleteId)
  const offline = chat.offline || demoOffline

  return (
    <div
      className="s2b app"
      data-theme={prefs.theme}
      data-collapsed={prefs.collapsed ? 'true' : 'false'}
      data-drawer={drawer ? 'open' : 'closed'}
      data-panel={panel ? 'open' : 'closed'}
      data-sheet={sheetFull ? 'full' : 'half'}
    >
      <Sidebar
        convs={chat.convs}
        activeId={chat.active?.id ?? null}
        dark={prefs.theme === 'dark'}
        tech={prefs.tech}
        onNew={newChat}
        onSelect={(id) => {
          chat.select(id)
          setFocusId(null)
          setSelSrc(1)
          setDrawer(false)
        }}
        onRename={chat.rename}
        onAskDelete={setDeleteId}
        onToggleCollapse={() => setPrefs((p) => ({ ...p, collapsed: !p.collapsed }))}
        onToggleTheme={() => setPrefs((p) => ({ ...p, theme: p.theme === 'dark' ? 'light' : 'dark' }))}
        onToggleTech={toggleTech}
        onDemo={demo}
      />

      <div
        className="scrim"
        onClick={() => {
          setDrawer(false)
          setPanel(null)
        }}
      />

      <main className="main">
        {offline && (
          <div className="banner" role="status">
            <span className="spinner" />
            Mất kết nối. Đang thử kết nối lại…
          </div>
        )}
        {!offline && apiDown && (
          <div className="banner" role="status">
            Không kết nối được máy chủ API. Chạy: uvicorn app.api:app --port 8000
          </div>
        )}
        <header className="topbar">
          <button className="btn btn--ghost btn--icon only-lt-xl" aria-label="Mở thanh bên" onClick={() => setDrawer(true)}>
            <Icon name="menu" lg />
          </button>
          <span className="topbar__title">{chat.active?.title ?? 'Cuộc trò chuyện mới'}</span>
          <span className="grow" />
          <button className="btn btn--ghost btn--icon only-lt-xl" aria-label="Cuộc trò chuyện mới" onClick={newChat}>
            <Icon name="plus" lg />
          </button>
        </header>

        <div className="scroll" ref={scroller}>
          <div className="col">
            {msgs.length === 0 && <Hero onAsk={(q) => send(q)} />}
            <div aria-live="polite" aria-label="Hội thoại">
              {msgs.map((m) =>
                m.role === 'user' ? (
                  <div className="msg" key={m.id}>
                    <div className="bubble">{m.text}</div>
                  </div>
                ) : (
                  <BotMessage
                    key={m.id}
                    m={m}
                    tech={prefs.tech}
                    canRetry={!chat.running}
                    onOpenSources={(n) => openSources(m, n)}
                    onOpenTech={() => {
                      setFocusId(m.id)
                      setPrefs((p) => ({ ...p, tech: true }))
                      setPanel('tech')
                      setSheetFull(false)
                    }}
                    onRetry={() => chat.retry(m.id)}
                    onRephrase={() => {
                      setInput(m.query)
                      window.setTimeout(() => composer.current?.focus(), 30)
                    }}
                    onSuggest={newChat}
                    onVote={(v, sent) =>
                      chat.patchBot(m.id, (b) => ({ ...b, vote: v, feedbackSent: sent ?? b.feedbackSent }))
                    }
                  />
                ),
              )}
            </div>
          </div>
        </div>

        <Composer
          ref={composer}
          value={input}
          running={chat.running}
          onChange={setInput}
          onSend={() => send(input)}
          onStop={chat.stop}
        />

        {delConv && (
          <div className="dialog-wrap">
            <div className="dialog" role="alertdialog" aria-labelledby="s2b-del-t">
              <h2 id="s2b-del-t">Xóa cuộc trò chuyện này?</h2>
              <p>
                “{delConv.title}” sẽ bị xóa khỏi lịch sử. Lịch sử chỉ lưu trên trình duyệt này, và mỗi câu hỏi được trả
                lời độc lập.
              </p>
              <div className="dialog__row">
                <button className="btn btn--outline" onClick={() => setDeleteId(null)} autoFocus>
                  Hủy
                </button>
                <button
                  className="btn btn--danger"
                  onClick={() => {
                    chat.remove(delConv.id)
                    setDeleteId(null)
                  }}
                >
                  Xóa
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      <Panel
        panel={panel}
        tech={prefs.tech}
        focus={focus}
        selSrc={selSrc}
        techTab={techTab}
        sheetFull={sheetFull}
        onSelSrc={setSelSrc}
        onPanel={setPanel}
        onTab={setTechTab}
        onSheet={setSheetFull}
      />
    </div>
  )
}

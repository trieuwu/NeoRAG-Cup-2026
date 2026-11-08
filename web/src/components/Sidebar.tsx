import { useState } from 'react'
import { type Conv, groupConvs } from '../lib/model'
import type { Demo } from '../lib/useChat'
import { Icon } from './Icon'

interface Props {
  convs: Conv[]
  activeId: string | null
  dark: boolean
  tech: boolean
  onNew: () => void
  onSelect: (id: string) => void
  onRename: (id: string, title: string) => void
  onAskDelete: (id: string) => void
  onToggleCollapse: () => void
  onToggleTheme: () => void
  onToggleTech: () => void
  onDemo: (kind: 'abstain' | Demo | 'offline' | 'long') => void
}

export function Sidebar(p: Props) {
  const [menuId, setMenuId] = useState<string | null>(null)
  const [renameId, setRenameId] = useState<string | null>(null)
  const [renameVal, setRenameVal] = useState('')
  const [demoOpen, setDemoOpen] = useState(false)
  const groups = groupConvs(p.convs)

  const commitRename = () => {
    if (renameId) p.onRename(renameId, renameVal)
    setRenameId(null)
  }

  return (
    <aside className="sidebar" aria-label="Thanh bên">
      <div className="sb-head">
        <span className="logo">
          <b>S2B</b>
          <span className="sb-hide-collapsed"> Hỏi Đáp</span>
        </span>
        <button
          className="btn btn--ghost btn--icon sb-collapse-btn"
          aria-label="Thu gọn hoặc mở rộng thanh bên"
          onClick={p.onToggleCollapse}
        >
          <Icon name="sidebar" />
        </button>
      </div>
      <button className="btn btn--primary newchat" onClick={p.onNew} aria-label="Cuộc trò chuyện mới">
        <Icon name="plus" />
        <span className="sb-hide-collapsed">Cuộc trò chuyện mới</span>
      </button>

      <nav className="history sb-hide-collapsed" aria-label="Lịch sử trò chuyện">
        {groups.length === 0 && <p className="empty-note">Chưa có cuộc trò chuyện nào.</p>}
        {groups.map((g) => (
          <div className="grp" key={g.label}>
            <h2 className="grp__label">{g.label}</h2>
            {g.items.map((c) => {
              const cur = c.id === p.activeId
              return (
                <div className={`conv ${cur ? 'is-current' : ''}`} key={c.id}>
                  {renameId === c.id ? (
                    <input
                      className="rename"
                      value={renameVal}
                      aria-label="Tên cuộc trò chuyện"
                      autoFocus
                      onChange={(e) => setRenameVal(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          commitRename()
                        } else if (e.key === 'Escape') {
                          e.stopPropagation()
                          setRenameId(null)
                        }
                      }}
                    />
                  ) : (
                    <>
                      <button
                        className="conv__btn"
                        onClick={() => p.onSelect(c.id)}
                        aria-current={cur ? 'page' : undefined}
                      >
                        <span className="conv__title">{c.title}</span>
                      </button>
                      <button
                        className="conv__more"
                        aria-label="Tùy chọn cuộc trò chuyện"
                        aria-haspopup="menu"
                        aria-expanded={menuId === c.id}
                        onClick={(e) => {
                          e.stopPropagation()
                          setMenuId(menuId === c.id ? null : c.id)
                        }}
                      >
                        <Icon name="more" style={{ strokeWidth: 2.6 }} />
                      </button>
                    </>
                  )}
                  {menuId === c.id && (
                    <div className="popover" role="menu">
                      <button
                        className="menu__item"
                        role="menuitem"
                        onClick={() => {
                          setRenameId(c.id)
                          setRenameVal(c.title)
                          setMenuId(null)
                        }}
                      >
                        <Icon name="pencil" />
                        Đổi tên
                      </button>
                      <button
                        className="menu__item menu__item--danger"
                        role="menuitem"
                        onClick={() => {
                          setMenuId(null)
                          p.onAskDelete(c.id)
                        }}
                      >
                        <Icon name="trash" />
                        Xóa
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="demo sb-hide-collapsed">
        <button className="demo__toggle" aria-expanded={demoOpen} onClick={() => setDemoOpen(!demoOpen)}>
          <span>Mô phỏng tình huống</span>
          <span className="badge club--nodau">demo</span>
        </button>
        {demoOpen && (
          <div className="demo__list">
            <button className="demo__item" onClick={() => p.onDemo('abstain')}>
              Câu hỏi ngoài tài liệu
            </button>
            <button className="demo__item" onClick={() => p.onDemo('retry')}>
              Lỗi quá tải (429)
            </button>
            <button className="demo__item" onClick={() => p.onDemo('timeout')}>
              Hết thời gian chờ
            </button>
            <button className="demo__item" onClick={() => p.onDemo('offline')}>
              Mất kết nối
            </button>
            <button className="demo__item" onClick={() => p.onDemo('long')}>
              Câu trả lời dài
            </button>
          </div>
        )}
      </div>

      <div className="sb-foot">
        <button className="switch" role="switch" aria-checked={p.dark} aria-label="Giao diện tối" onClick={p.onToggleTheme}>
          <span className="switch__l">
            <Icon name="moon" />
            <span className="sb-hide-collapsed">Giao diện tối</span>
          </span>
          <span className="switch__track" />
        </button>
        <button className="switch" role="switch" aria-checked={p.tech} aria-label="Chế độ kỹ thuật" onClick={p.onToggleTech}>
          <span className="switch__l">
            <Icon name="flow" />
            <span className="sb-hide-collapsed">Chế độ kỹ thuật</span>
          </span>
          <span className="switch__track" />
        </button>
      </div>
    </aside>
  )
}

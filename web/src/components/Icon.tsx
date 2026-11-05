// Biểu tượng nét (cùng bộ path với prototype Claude Design).
export const ICON = {
  check: 'M20 6 9 17l-5-5',
  x: 'M18 6 6 18M6 6l12 12',
  send: 'M12 19V5M5 12l7-7 7 7',
  plus: 'M12 5v14M5 12h14',
  menu: 'M4 6h16M4 12h16M4 18h16',
  sidebar: 'M3 5h18v14H3zM9 5v14',
  copy: 'M9 9h10v10H9zM5 15V5h10',
  up: 'M7 11v9H4v-9h3zM7 11l4-8c1.5 0 2.5 1 2.2 2.6L12.8 9H19a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.8 20H7',
  down: 'M17 13V4h3v9h-3zM17 13l-4 8c-1.5 0-2.5-1-2.2-2.6L11.2 15H5a2 2 0 0 1-2-2.3l1.2-7A2 2 0 0 1 6.2 4H17',
  book: 'M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zM4 19a2 2 0 0 1 2-2h13',
  flow: 'M4 5h6v5H4zM14 14h6v5h-6zM10 7.5h2a2 2 0 0 1 2 2V14',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
  chevL: 'M15 18l-6-6 6-6',
  chevR: 'M9 18l6-6-6-6',
  chevD: 'M6 9l6 6 6-6',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  info: 'M12 8h.01M11 12h1v5h1M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  alert: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  alertCircle: 'M12 9v4M12 17h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  refresh: 'M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5',
  search: 'M21 21l-4.3-4.3M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0z',
  bars: 'M5 20V10M12 20V4M19 20v-7',
  spark: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z',
  help: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  pencil: 'M4 20h4L19 9l-4-4L4 16v4zM13 7l4 4',
  arrowR: 'M5 12h14M13 6l6 6-6 6',
  sortUp: 'M12 19V5M6 11l6-6 6 6',
  sortDown: 'M12 5v14M6 13l6 6 6-6',
  stop: 'M6 6h12v12H6z',
} as const

export type IconName = keyof typeof ICON

export function Icon({
  name,
  lg,
  fill,
  size,
  style,
}: {
  name: IconName
  lg?: boolean
  fill?: boolean
  size?: number
  style?: React.CSSProperties
}) {
  const cls = ['ic', lg && 'ic--lg', fill && 'ic--fill'].filter(Boolean).join(' ')
  return (
    <svg
      className={cls}
      viewBox="0 0 24 24"
      aria-hidden="true"
      style={size ? { width: size, height: size, ...style } : style}
    >
      <path d={ICON[name]} />
    </svg>
  )
}

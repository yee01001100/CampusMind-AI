import type { ReactNode, SVGProps } from 'react'

export type IconName =
  | 'home'
  | 'notice'
  | 'calendar'
  | 'chat'
  | 'bell'
  | 'spark'
  | 'clock'
  | 'check'
  | 'alert'
  | 'arrow'
  | 'book'
  | 'map'
  | 'source'
  | 'send'
  | 'refresh'
  | 'wifi'
  | 'tool'
  | 'close'

const paths: Record<IconName, ReactNode> = {
  home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9"/><path d="M9 20v-6h6v6"/></>,
  notice: <><path d="M6 4h12v16H6z"/><path d="M9 8h6M9 12h6M9 16h4"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
  chat: <><path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
  spark: <><path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  alert: <><path d="M12 3 2.7 20h18.6z"/><path d="M12 9v4M12 17h.01"/></>,
  arrow: <><path d="M5 12h14"/><path d="m15 8 4 4-4 4"/></>,
  book: <><path d="M4 4h6a3 3 0 0 1 3 3v13a3 3 0 0 0-3-3H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a3 3 0 0 1 3-3h6z"/></>,
  map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/></>,
  source: <><path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/></>,
  send: <><path d="m3 3 18 9-18 9 4-9z"/><path d="M7 12h14"/></>,
  refresh: <><path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M6.1 8a7 7 0 0 1 11.8-2L20 8M4 16l2.1 2a7 7 0 0 0 11.8-2"/></>,
  wifi: <><path d="M5 12.5a10 10 0 0 1 14 0M8 16a6 6 0 0 1 8 0M12 20h.01"/></>,
  tool: <><path d="M14.7 6.3a4 4 0 0 0-5-5l2.1 2.1-2.4 2.4-2.1-2.1a4 4 0 0 0 5 5L19 15.4a2.5 2.5 0 1 1-3.6 3.6l-6.7-6.7"/></>,
  close: <><path d="M6 6l12 12M18 6 6 18"/></>,
}

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>
      {paths[name]}
    </svg>
  )
}

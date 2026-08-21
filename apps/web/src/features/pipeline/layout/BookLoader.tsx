import { createContext, useContext, type ReactNode } from "react"

const PAGE_PATH =
  "M90,0 L90,120 L11,120 C4.92486775,120 0,115.075132 0,109 L0,11 C0,4.92486775 4.92486775,0 11,0 L90,0 Z M71.5,81 L18.5,81 C17.1192881,81 16,82.1192881 16,83.5 C16,84.8254834 17.0315359,85.9100387 18.3356243,85.9946823 L18.5,86 L71.5,86 C72.8807119,86 74,84.8807119 74,83.5 C74,82.1745166 72.9684641,81.0899613 71.6643757,81.0053177 L71.5,81 Z M71.5,57 L18.5,57 C17.1192881,57 16,58.1192881 16,59.5 C16,60.8254834 17.0315359,61.9100387 18.3356243,61.9946823 L18.5,62 L71.5,62 C72.8807119,62 74,60.8807119 74,59.5 C74,58.1192881 72.8807119,57 71.5,57 Z M71.5,33 L18.5,33 C17.1192881,33 16,34.1192881 16,35.5 C16,36.8254834 17.0315359,37.9100387 18.3356243,37.9946823 L18.5,38 L71.5,38 C72.8807119,38 74,36.8807119 74,35.5 C74,34.1192881 72.8807119,33 71.5,33 Z"

type Props = {
  detail?: string
  label: string
  phase?: "enter" | "exit"
  variant?: "overlay" | "panel" | "compact"
}

const OverlayLoaderContext = createContext(false)

export function BookLoaderLayer({
  children,
  overlayVisible,
}: {
  children: ReactNode
  overlayVisible: boolean
}) {
  return (
    <OverlayLoaderContext.Provider value={overlayVisible}>
      {children}
    </OverlayLoaderContext.Provider>
  )
}

export function BookLoader({
  detail,
  label,
  phase = "enter",
  variant = "panel",
}: Props) {
  const overlayVisible = useContext(OverlayLoaderContext)
  if (overlayVisible && variant !== "overlay") return null

  return (
    <div
      className={`book-loader-shell book-loader-${phase} book-loader-${variant}`}
      role="status"
      aria-busy="true"
      aria-live="polite"
    >
      <div className="book-loader-glass">
        <div className="book-loader-mark" aria-hidden="true">
          <div className="book-loader-cover">
            <ul>
              {Array.from({ length: 6 }, (_, index) => (
                <li key={index}>
                  <svg fill="currentColor" viewBox="0 0 90 120">
                    <path d={PAGE_PATH} />
                  </svg>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <strong>{label}</strong>
        {detail && <span>{detail}</span>}
      </div>
    </div>
  )
}

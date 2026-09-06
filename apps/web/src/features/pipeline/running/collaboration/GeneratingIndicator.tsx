export function GeneratingIndicator({
  compact = false,
}: {
  compact?: boolean
}) {
  const letters = Array.from("Generating")
  return (
    <div
      aria-label="正在生成"
      className={`collaboration-generating${compact ? " compact" : ""}`}
      role="status"
    >
      <span aria-hidden="true" className="collaboration-generating-ring" />
      <span aria-hidden="true" className="collaboration-generating-word">
        {letters.map((letter, index) => (
          <i
            key={`${letter}-${index}`}
            style={{ animationDelay: `${index * 70}ms` }}
          >
            {letter}
          </i>
        ))}
      </span>
      <span className="sr-only">正在生成协作回复</span>
    </div>
  )
}

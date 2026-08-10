type Props = {
  label: string;
  onChange: (value: string) => void;
  readOnly: boolean;
  totalChapters?: number;
  value: string;
};

export function CharacterChapterWindowField({ label, onChange, readOnly, totalChapters, value }: Props) {
  const window = parseChapterWindow(value);
  const boundedEnd = boundedChapter(window.end, totalChapters);
  const updateStart = (next: number) => {
    const start = boundedChapter(next, totalChapters);
    onChange(formatChapterWindow(start, Math.max(start, boundedEnd)));
  };
  const updateEnd = (next: number) => {
    const end = Math.max(window.start, boundedChapter(next, totalChapters));
    onChange(formatChapterWindow(window.start, end));
  };
  return (
    <fieldset className="character-chapter-window">
      <legend>{label}</legend>
      <label>
        <span>最早</span>
        <input aria-label={`${label}最早章节`} max={totalChapters} min={1} onChange={(event) => updateStart(event.target.valueAsNumber)} readOnly={readOnly} step={1} type="number" value={window.start} />
      </label>
      <i aria-hidden="true">-</i>
      <label>
        <span>最晚</span>
        <input aria-label={`${label}最晚章节`} max={totalChapters} min={window.start} onChange={(event) => updateEnd(event.target.valueAsNumber)} readOnly={readOnly} step={1} type="number" value={window.end} />
      </label>
    </fieldset>
  );
}

export function formatCharacterChapterWindow(value: string) {
  const window = parseChapterWindow(value);
  return window.start === window.end ? `第 ${window.start} 章` : `第 ${window.start}-${window.end} 章`;
}

export function parseChapterWindow(value: string) {
  const match = /^chapter:([1-9]\d*)(?:-([1-9]\d*))?$/.exec(value);
  const start = Number(match?.[1] ?? 1);
  const end = Math.max(start, Number(match?.[2] ?? start));
  return { end, start };
}

function boundedChapter(value: number, totalChapters?: number) {
  const normalized = Number.isFinite(value) ? Math.max(1, Math.floor(value)) : 1;
  return totalChapters ? Math.min(normalized, totalChapters) : normalized;
}

function formatChapterWindow(start: number, end: number) {
  return start === end ? `chapter:${start}` : `chapter:${start}-${end}`;
}

export type StreamRevealMode = 'line' | 'prose' | 'smooth' | 'word';

export const STREAM_REVEAL_BACKLOG_LIMIT = 420;
export const STREAM_REVEAL_BOOST_BACKLOG = 140;

export type StreamRevealPace = 'steady' | 'boost';

/** backlog 加速档位信号：渲染层据此把新词切到 blur→sharp 变体掩盖成批感。 */
export function streamRevealPace(backlog: number): StreamRevealPace {
  return backlog > STREAM_REVEAL_BOOST_BACKLOG ? 'boost' : 'steady';
}

type StreamRevealContext = {
  active: boolean;
  backlog: number;
  documentHidden: boolean;
  reducedMotion: boolean;
};

export function shouldCompleteStreamReveal({ active, backlog, documentHidden, reducedMotion }: StreamRevealContext) {
  return !active || reducedMotion || documentHidden || backlog >= STREAM_REVEAL_BACKLOG_LIMIT;
}

export function nextRevealLength(current: string, target: string, mode: StreamRevealMode) {
  if (current.length >= target.length) return target.length;
  const remaining = target.slice(current.length);
  const preferred = mode === 'line'
    ? lineRevealSize(remaining)
    : mode === 'smooth'
      ? smoothRevealSize(remaining)
      : mode === 'word'
        ? wordRevealSize(remaining)
        : proseRevealSize(remaining);
  const backlog = target.length - current.length;
  const accelerated = backlog > 260 ? Math.max(preferred, 42) : backlog > STREAM_REVEAL_BOOST_BACKLOG ? Math.max(preferred, 28) : preferred;
  return Math.min(target.length, current.length + accelerated);
}

export function splitStreamBlocks(value: string) {
  const normalized = value.replace(/\r/g, '');
  const blocks = normalized.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  if (blocks.length) return blocks;
  return normalized.trim() ? [normalized.trim()] : [];
}

export function splitReadableUnits(value: string, maxUnitLength = 88) {
  const blocks = splitStreamBlocks(value);
  const units = blocks.flatMap((block) => {
    const sentences = splitSentences(block);
    if (!sentences.length) return [block];
    return sentences.flatMap((sentence) => splitLongUnit(sentence, maxUnitLength));
  });
  return units.map((item) => item.trim()).filter(Boolean);
}

export function splitStreamingLines(value: string, maxLineLength = 64) {
  const units = splitReadableUnits(value, Math.max(maxLineLength, 72));
  const lines: string[] = [];
  let current = '';
  units.forEach((unit) => {
    const next = current ? `${current}${unit}` : unit;
    if (next.length <= maxLineLength || !current) {
      current = next;
      return;
    }
    lines.push(current);
    current = unit;
  });
  if (current.trim()) lines.push(current);
  return lines.map((line) => line.trim()).filter(Boolean);
}

export function compactStreamPreview(value: string, maxBlocks = 4) {
  const blocks = splitStreamBlocks(value);
  if (blocks.length > 1) return blocks.slice(-maxBlocks).join('\n');
  return splitSentences(value).slice(-maxBlocks).join('\n');
}

function proseRevealSize(value: string) {
  const punctuation = value.search(/[。！？；.!?;]\s*/);
  if (punctuation >= 6 && punctuation <= 54) return punctuation + 1;
  const comma = value.search(/[，、,]\s*/);
  if (comma >= 10 && comma <= 34) return comma + 1;
  return Math.min(value.length, 14);
}

function lineRevealSize(value: string) {
  const newline = value.indexOf('\n');
  if (newline >= 0 && newline <= 90) return newline + 1;
  return proseRevealSize(value);
}

function smoothRevealSize(value: string) {
  const punctuation = value.search(/[。！？；.!?;]\s*/);
  if (punctuation >= 8 && punctuation <= 96) return punctuation + 1;
  const comma = value.search(/[，、,]\s*/);
  if (comma >= 24 && comma <= 68) return comma + 1;
  const whitespace = value.search(/\s+/);
  if (whitespace >= 28 && whitespace <= 72) return whitespace + 1;
  return Math.min(value.length, 38);
}

/**
 * 词级消费的小步长断点：优先落在句读 / 逗顿 / 空白，兜底 12 字。
 * 每 tick 只放出 1-6 个词块，让词级 fade 呈连续流而非整行成批；
 * 句读粒度模式（prose/smooth/line）保留为 fallback。
 */
function wordRevealSize(value: string) {
  const punctuation = value.search(/[。！？；.!?;]\s*/);
  if (punctuation >= 4 && punctuation <= 26) return punctuation + 1;
  const comma = value.search(/[，、,]\s*/);
  if (comma >= 4 && comma <= 22) return comma + 1;
  const whitespace = value.search(/\s+/);
  if (whitespace >= 4 && whitespace <= 18) return whitespace + 1;
  return Math.min(value.length, 12);
}

function splitSentences(value: string) {
  return value
    .split(/(?<=[。！？；.!?;])\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitLongUnit(value: string, maxLength: number) {
  if (value.length <= maxLength) return [value];
  const units: string[] = [];
  let rest = value;
  while (rest.length > maxLength) {
    const slice = rest.slice(0, maxLength);
    const cut = Math.max(slice.lastIndexOf('，'), slice.lastIndexOf('、'), slice.lastIndexOf(','), slice.lastIndexOf(' '));
    const index = cut > 24 ? cut + 1 : maxLength;
    units.push(rest.slice(0, index));
    rest = rest.slice(index);
  }
  if (rest.trim()) units.push(rest);
  return units;
}

export type StreamWordToken = { key: number; text: string };

export type StreamWordVariant = 'fade' | 'blur';

// CJK 统一表意区（含扩展 A、部首补充、兼容区）。
const CJK_CHAR = /[⺀-⻿㐀-䶿一-鿿豈-﫿]/;
// 开引类标点：并入其后的词块（避免行首孤立的开引号 span）。
const OPENING_PUNCT = /[「『（【《〈“‘"'([{]/;
// 句读 / 闭引类标点：吸附到前一个词块（不产生裸标点动画节点）。
const CLOSING_PUNCT = /[，。！？；：、）」』】》〉”’…—,.!?;:)\]}]/;

/**
 * 把流式前缀切成词级 token：中文按 2-4 字词块、英文按空格词、标点吸附到相邻词块。
 * key 为 token 的起始偏移。分词只依赖已出现的字符与固定偏移规则（不做词典分词），
 * 因此对「只增不改」的流式前缀满足稳定性合同：已产出的 token key 永不变，
 * 文本只会在尾部 token 上单调延长——React 以 key 复用节点，已 reveal 的词不会重播动画。
 */
export function splitStreamWords(value: string): StreamWordToken[] {
  const tokens: StreamWordToken[] = [];
  let index = 0;
  while (index < value.length) {
    const start = index;
    while (index < value.length && /\s/.test(value[index])) index += 1;
    while (index < value.length && OPENING_PUNCT.test(value[index])) index += 1;
    index = consumeWord(value, index);
    while (index < value.length && CLOSING_PUNCT.test(value[index])) index += 1;
    if (index === start) index += 1;
    tokens.push({ key: start, text: value.slice(start, index) });
  }
  return tokens;
}

/**
 * 同步「词块 → 入场变体」缓存：新出现的 key 以当前档位定格（fade / blur），
 * 已挂载的 key 保持首次赋予的变体（避免 backlog 档位切换时改 className 重播动画），
 * 已消失的 key（章节切换 / 流重置）被清除。
 */
export function syncStreamWordVariants(
  variants: Map<number, StreamWordVariant>,
  tokens: StreamWordToken[],
  variant: StreamWordVariant,
): Map<number, StreamWordVariant> {
  const alive = new Set(tokens.map((token) => token.key));
  variants.forEach((_, key) => {
    if (!alive.has(key)) variants.delete(key);
  });
  tokens.forEach((token) => {
    if (!variants.has(token.key)) variants.set(token.key, variant);
  });
  return variants;
}

function consumeWord(value: string, index: number) {
  if (index >= value.length) return index;
  const char = value[index];
  if (CJK_CHAR.test(char)) {
    // 词块目标长度 2-4，由起始偏移决定（确定、无回溯，保证前缀稳定）。
    const size = 2 + (index % 3);
    let end = index;
    while (end < value.length && end - index < size && CJK_CHAR.test(value[end])) end += 1;
    return end;
  }
  if (/\s/.test(char) || OPENING_PUNCT.test(char) || CLOSING_PUNCT.test(char)) return index;
  let end = index;
  while (
    end < value.length
    && !/\s/.test(value[end])
    && !CJK_CHAR.test(value[end])
    && !OPENING_PUNCT.test(value[end])
    && !CLOSING_PUNCT.test(value[end])
  ) end += 1;
  return end;
}

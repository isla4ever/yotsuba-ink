export type WritingViewportSnapshot = {
  following: boolean;
  scrollTop: number;
  selectionEnd: number;
  selectionStart: number;
};

/**
 * 正文阅读容器：定稿/可编辑态是 textarea；流式态换成词级渲染的滚动 div。
 * 两者共享滚动跟随合同（上滚脱钩 + 回到生成位置），选区能力只有 textarea 具备。
 */
export type ManuscriptReaderElement = HTMLTextAreaElement | HTMLDivElement;

export function isSelectableReader(reader: ManuscriptReaderElement): reader is HTMLTextAreaElement {
  return 'setSelectionRange' in reader;
}

export function readerContentLength(reader: ManuscriptReaderElement) {
  return isSelectableReader(reader) ? reader.value.length : reader.textContent?.length ?? 0;
}

const WRITING_TAIL_THRESHOLD = 36;

export function isWritingViewportAtTail(
  scrollHeight: number,
  scrollTop: number,
  clientHeight: number,
) {
  return scrollHeight - scrollTop - clientHeight <= WRITING_TAIL_THRESHOLD;
}

export function clampWritingViewport(
  snapshot: WritingViewportSnapshot | undefined,
  contentLength: number,
): WritingViewportSnapshot {
  const limit = Math.max(0, contentLength);
  const start = Math.min(Math.max(0, snapshot?.selectionStart ?? 0), limit);
  const end = Math.min(Math.max(start, snapshot?.selectionEnd ?? start), limit);
  return {
    following: snapshot?.following ?? true,
    scrollTop: Math.max(0, snapshot?.scrollTop ?? 0),
    selectionStart: start,
    selectionEnd: end,
  };
}

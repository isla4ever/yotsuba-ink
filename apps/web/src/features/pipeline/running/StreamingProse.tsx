import { useRef } from 'react';
import type { StreamRevealPace } from '../lib/streamText';
import { splitStreamWords, syncStreamWordVariants, type StreamWordVariant } from '../lib/streamWords';

type StreamingProseProps = {
  pace: StreamRevealPace;
  text: string;
};

/**
 * 流式词级渲染层（Phase 11.3）：只在流式进行中挂载。
 * - token key = 起始偏移（splitStreamWords 保证前缀稳定），已 reveal 的词不重播动画；
 * - 入场变体在词块首次出现时按当前 backlog 档位定格（fade 150ms / blur→sharp 150ms），
 *   档位切换不改已挂载 span 的 className，避免 animation-name 变化触发重播；
 * - 流结束由上层（WritingManuscriptEditor）切回纯文本 textarea——已完成章节零动画 DOM。
 */
export function StreamingProse({ pace, text }: StreamingProseProps) {
  const variantsRef = useRef<Map<number, StreamWordVariant>>(new Map());
  const tokens = splitStreamWords(text);
  // render 期同步缓存：幂等（同一 token 集合重复同步结果一致），StrictMode 双渲染安全。
  const variants = syncStreamWordVariants(variantsRef.current, tokens, pace === 'boost' ? 'blur' : 'fade');
  return (
    <>
      {tokens.map((token) => (
        <span
          className={variants.get(token.key) === 'blur' ? 'stream-word stream-word-blur' : 'stream-word'}
          key={token.key}
        >
          {token.text}
        </span>
      ))}
      <span aria-hidden="true" className="writing-caret-tail" />
    </>
  );
}

type StreamingSkeletonProps = {
  label: string;
};

/** 首 token 前空窗骨架：3 行宽度递减 shimmer（100%/86%/64%），首 token 到达即由上层卸载。 */
export function StreamingSkeleton({ label }: StreamingSkeletonProps) {
  return (
    <div aria-label={label} className="stream-skeleton" role="status">
      <span className="stream-skeleton-row" />
      <span className="stream-skeleton-row" />
      <span className="stream-skeleton-row" />
    </div>
  );
}

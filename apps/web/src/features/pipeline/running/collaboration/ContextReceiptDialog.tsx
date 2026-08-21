import * as Dialog from '@radix-ui/react-dialog';
import { Check, Database, FileText, X } from 'lucide-react';
import type { CollaborationContextReceipt, ContextSourceReceipt } from "../../contracts/authorCollaboration"

type Props = {
  confirmPending: boolean;
  disabled?: boolean;
  onCancelPending?: () => void;
  onConfirm?: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  pendingMessage?: string;
  receipt: CollaborationContextReceipt | null;
};

export function ContextReceiptDialog({ confirmPending, disabled, onCancelPending, onConfirm, onOpenChange, open, pendingMessage = '', receipt }: Props) {
  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay className="collaboration-dialog-overlay" />
        <Dialog.Content aria-describedby="collaboration-receipt-description" className="collaboration-receipt-dialog">
          <header>
            <div>
              <p className="eyebrow">Context Receipt</p>
              <Dialog.Title>本轮上下文回执</Dialog.Title>
              <Dialog.Description id="collaboration-receipt-description">发送前确认模型会读取的来源、范围与预算。</Dialog.Description>
            </div>
            <Dialog.Close aria-label="关闭上下文回执"><X size={17} /></Dialog.Close>
          </header>
          {receipt ? (
            <>
              <div className="collaboration-receipt-summary">
                <div><Database size={14} /><span>已采用来源</span><strong>{receipt.sources.filter((item) => item.disposition !== 'omitted').length}</strong></div>
                <div><FileText size={14} /><span>预计上下文</span><strong>{receipt.token_estimate.toLocaleString()} tokens</strong></div>
                <div><span>模型</span><strong>{receipt.provider_profile_id} · {receipt.model}</strong></div>
              </div>
              <div className="collaboration-receipt-body">
                {confirmPending && pendingMessage ? (
                  <div className="collaboration-receipt-request">
                    <span>待发送请求</span>
                    <p>{pendingMessage}</p>
                  </div>
                ) : null}
                {receipt.sources.map((source) => <ReceiptSource key={`${source.category}-${source.source_ref}`} source={source} />)}
              </div>
              <footer>
                <span>{receipt.used_chars.toLocaleString()} / {receipt.budget_chars.toLocaleString()} 字符预算</span>
                <div>
                  {confirmPending ? <button className="ghost" disabled={disabled} onClick={onCancelPending} type="button">放弃本次</button> : <Dialog.Close className="ghost" type="button">返回工作台</Dialog.Close>}
                  {confirmPending ? <button className="primary" disabled={disabled} onClick={onConfirm} type="button"><Check size={14} />确认并发送</button> : null}
                </div>
              </footer>
            </>
          ) : <div className="collaboration-receipt-empty">当前线程还没有可查看的上下文回执。</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ReceiptSource({ source }: { source: ContextSourceReceipt }) {
  return (
    <article className="collaboration-receipt-source" data-disposition={source.disposition}>
      <div><span>{categoryLabel(source.category)}</span><strong>{source.label}</strong></div>
      <p>{source.reason}</p>
      <small>{source.char_count.toLocaleString()} 字符 · 约 {source.token_estimate.toLocaleString()} tokens · {source.disposition === 'required' ? '必需' : source.disposition === 'optional' ? '已采用' : '已排除'}</small>
    </article>
  );
}

function categoryLabel(category: ContextSourceReceipt['category']) {
  return ({
    selection: '明确选区', artifact: '当前产物', upstream: '上游约束', characters: '人物', continuity: '连续性',
    canon_wiki: 'Canon / Wiki', foreshadow: '伏笔', knowledge: '知识库', craft: '写作机制', author_preferences: '作者偏好', history: '对话历史',
  } as const)[category];
}

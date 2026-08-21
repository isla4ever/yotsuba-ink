import {
  AssistantRuntimeProvider,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react';
import { Check, Clipboard, ListChecks, Quote, Sparkles } from 'lucide-react';
import { useEffect } from 'react';
import type { CollaborationMessage, SelectionAnchor } from "../../contracts/authorCollaboration"
import type { KnowledgeDocument } from "../../contracts/knowledge"
import { messagePatch, patchBeforeText } from '../../lib/authorCollaborationProjection';
import type { AuthorCollaborationController } from '../../state/useAuthorCollaboration';
import { CollaborationComposer } from './CollaborationComposer';
import { GeneratingIndicator } from './GeneratingIndicator';
import { PatchCandidateView } from './PatchCandidateView';
import { CollaborationTurnOutcome } from './CollaborationTurnOutcome';

type Props = {
  canRevise: boolean;
  collaboration: AuthorCollaborationController;
  knowledgeDocuments: KnowledgeDocument[];
  onClearSelection: () => void;
  onOpenKnowledgeManager: () => void;
  onOpenReceipt: () => void;
  selection: SelectionAnchor | null;
};

export function CollaborationThread({ canRevise, collaboration, knowledgeDocuments, onClearSelection, onOpenKnowledgeManager, onOpenReceipt, selection }: Props) {
  const runtime = useExternalStoreRuntime<CollaborationMessage>({
    isDisabled: collaboration.activeThread?.status !== 'active',
    isLoading: collaboration.loading,
    isRunning: collaboration.isStreaming,
    isSendDisabled: collaboration.actionPending || Boolean(collaboration.pendingSubmission) || (collaboration.mode === 'revise' && (!selection || !canRevise)),
    messages: collaboration.detail?.messages ?? [],
    convertMessage: convertCollaborationMessage,
    onCancel: collaboration.cancel,
    onNew: (message: AppendMessage) => collaboration.submit(message, selection),
  });
  const UserMessage = () => <CollaborationMessageView collaboration={collaboration} role="user" />;
  const AssistantMessage = () => <CollaborationMessageView collaboration={collaboration} role="assistant" />;
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ComposerDraftBridge draft={collaboration.composerDraft} />
      <ThreadPrimitive.Root className="collaboration-thread">
        <ThreadPrimitive.Viewport className="collaboration-thread-viewport">
          <ThreadPrimitive.Empty>
            <div className="collaboration-empty-state">
              <span><Sparkles size={18} /></span>
              <strong>从局部问题开始</strong>
              <p>讨论因果、人物动机或语言质地；需要改稿时先选择当前字段中的原文。</p>
            </div>
          </ThreadPrimitive.Empty>
          <ThreadPrimitive.Messages components={{ AssistantMessage, UserMessage }} />
          {collaboration.isStreaming ? <div className="collaboration-generating-row"><GeneratingIndicator /></div> : null}
          <ThreadPrimitive.ViewportFooter className="collaboration-thread-footer">
            <CollaborationComposer
              canRevise={canRevise}
              contextPolicy={collaboration.contextPolicy}
              disabled={collaboration.activeThread?.status !== 'active'}
              isStreaming={collaboration.isStreaming}
              knowledgeDocuments={knowledgeDocuments}
              latestReceipt={collaboration.latestReceipt}
              mode={collaboration.mode}
              onClearSelection={onClearSelection}
              onDraftChange={collaboration.setComposerDraft}
              onModeChange={collaboration.setMode}
              onOpenKnowledgeManager={onOpenKnowledgeManager}
              onOpenReceipt={onOpenReceipt}
              selection={selection}
              setContextOption={collaboration.setContextOption}
              toggleKnowledgeSource={collaboration.toggleKnowledgeSource}
            />
          </ThreadPrimitive.ViewportFooter>
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

function ComposerDraftBridge({ draft }: { draft: string }) {
  const aui = useAui();
  useEffect(() => {
    const state = aui.composer.getState();
    if (state.isEditing && state.text !== draft) aui.composer.setText(draft);
  }, [aui, draft]);
  return null;
}

function CollaborationMessageView({ collaboration, role }: { collaboration: AuthorCollaborationController; role: 'user' | 'assistant' }) {
  const messageId = useAuiState((state) => state.message.id);
  const message = collaboration.detail?.messages.find((item) => item.message_id === messageId);
  if (!message) return null;
  const turn = collaboration.detail?.turns.find((item) => item.turn_id === message.turn_id);
  const patch = messagePatch(collaboration.detail, message);
  return (
    <MessagePrimitive.Root className={`collaboration-message ${role}`}>
      <header>
        <span>{role === 'user' ? '作者' : '协作编辑'}</span>
        <small>{modeLabel(message.mode)} · {formatTime(message.created_at)}</small>
      </header>
      {role === 'user' && turn?.selection_anchor ? (
        <div className="collaboration-message-selection"><Quote size={12} /><span>已引用 {turn.selection_anchor.selected_char_count} 字</span><code>{turn.selection_anchor.field_path}</code></div>
      ) : null}
      <MessagePrimitive.Parts />
      {role === 'user' && turn && !turn.assistant_message_ref ? <CollaborationTurnOutcome turn={turn} /> : null}
      {message.plan ? (
        <section className="collaboration-plan">
          <header><ListChecks size={14} /><strong>{message.plan.goal}</strong></header>
          <ol>{message.plan.steps.map((step) => <li key={step}>{step}</li>)}</ol>
          {message.plan.risks.length ? <p>风险：{message.plan.risks.join('；')}</p> : null}
        </section>
      ) : null}
      {patch ? (
        <PatchCandidateView
          before={patchBeforeText(collaboration.detail, patch)}
          disabled={collaboration.actionPending}
          onAccept={() => { void collaboration.patchDecision(patch, 'accept'); }}
          onReject={() => { void collaboration.patchDecision(patch, 'reject'); }}
          patch={patch}
        />
      ) : null}
      {role === 'assistant' ? (
        <footer className="collaboration-message-actions">
          <button onClick={() => { void navigator.clipboard.writeText(message.content); }} title="复制回复" type="button"><Clipboard size={13} />复制</button>
          <button onClick={() => collaboration.setMode('plan')} type="button"><Check size={13} />转为方案</button>
        </footer>
      ) : null}
    </MessagePrimitive.Root>
  );
}

function convertCollaborationMessage(message: CollaborationMessage): ThreadMessageLike {
  return {
    id: message.message_id,
    role: message.role,
    content: message.content,
    createdAt: new Date(message.created_at),
    status: message.role === 'assistant' ? assistantStatus(message) : undefined,
    metadata: { custom: { mode: message.mode, turnId: message.turn_id } },
  };
}

function assistantStatus(message: CollaborationMessage): NonNullable<ThreadMessageLike['status']> {
  if (message.status === 'partial') return { type: 'running' };
  if (message.status === 'cancelled') return { type: 'incomplete', reason: 'cancelled' };
  if (message.status === 'failed') return { type: 'incomplete', reason: 'error' };
  return { type: 'complete', reason: 'stop' };
}

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(date);
}

function modeLabel(mode: CollaborationMessage['mode']) {
  return mode === 'discuss' ? '讨论' : mode === 'plan' ? '方案' : '改稿';
}

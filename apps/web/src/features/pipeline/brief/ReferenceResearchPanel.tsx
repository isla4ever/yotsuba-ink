import { useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { DatabaseZap, ExternalLink, Globe2, Link2, RefreshCw, Settings2, X } from 'lucide-react';
import type { KnowledgeDocument, KnowledgeSearchResult, ReferenceSearchResult, WorkflowStage } from '../contracts';
import { LoadingButton } from '../layout/LoadingButton';
import { addTagValue, removeTagValue, updateStageInputDefault } from '../lib/stageConfig';
import { searchKnowledgeReferences, searchWebReferences } from '../services/referenceApi';
import { ReferenceModeTabs, type ReferenceMode } from './ReferenceModeTabs';

type ViewResult = {
  id: string;
  title: string;
  preview: string;
  source: 'web' | 'knowledge';
  url?: string;
  section?: string;
};

type SearchState = {
  status: 'idle' | 'loading' | 'success' | 'empty' | 'error';
  message: string;
  results: ViewResult[];
  retry: 'smart' | 'knowledge' | null;
};

type Props = {
  stage: WorkflowStage;
  knowledgeDocuments: KnowledgeDocument[];
  onOpenKnowledgeManager?: () => void;
  onChange: (stage: WorkflowStage) => void;
};

const idleState: SearchState = { status: 'idle', message: '', results: [], retry: null };

export function ReferenceResearchPanel({ stage, knowledgeDocuments, onChange, onOpenKnowledgeManager }: Props) {
  const mode = String(fieldValue(stage, 'reference_mode') || 'smart_search') as ReferenceMode;
  const [searchState, setSearchState] = useState<SearchState>(idleState);
  const requestRef = useRef(0);
  const stageRef = useRef(stage);
  const tabsId = useId();
  stageRef.current = stage;
  const keywords = asStringArray(fieldValue(stage, 'reference_keywords'));
  const urls = asStringArray(fieldValue(stage, 'reference_urls'));
  const docIds = asStringArray(fieldValue(stage, 'knowledge_base_doc_ids'));
  const projectId = knowledgeDocuments[0]?.project_id ?? '';
  const webEnabled = Boolean(fieldValue(stage, 'enable_web_search'));
  const intent = String(fieldValue(stage, 'reference_query_intent') || '');
  const selectedMode = useMemo(() => modes.find((item) => item.key === mode) ?? modes[0], [mode]);

  const updateMode = (nextMode: ReferenceMode) => {
    requestRef.current += 1;
    onChange(updateStageInputDefault(stage, 'reference_mode', nextMode));
    setSearchState(idleState);
  };

  const runSmartSearch = async () => {
    const query = keywords.join(' ').trim();
    if (!query) {
      setSearchState({ status: 'error', message: '请先录入 1-3 个参考关键词。', results: [], retry: null });
      return;
    }
    const requestId = ++requestRef.current;
    setSearchState({ status: 'loading', message: '正在检索真实来源与项目资料...', results: [], retry: 'smart' });
    const tasks: Array<{ source: 'web' | 'knowledge'; request: Promise<unknown> }> = [];
    if (webEnabled) tasks.push({ source: 'web', request: searchWebReferences(query, 5) });
    if (projectId) tasks.push({ source: 'knowledge', request: searchKnowledgeReferences({ query, intent, projectId, docIds, topK: 6 }) });
    if (!tasks.length) {
      setSearchState({ status: 'error', message: '请先上传项目资料，或开启公开网页检索。', results: [], retry: null });
      return;
    }
    const settled = await Promise.allSettled(tasks.map((task) => task.request));
    if (requestId !== requestRef.current) return;
    const webIndex = tasks.findIndex((task) => task.source === 'web');
    const knowledgeIndex = tasks.findIndex((task) => task.source === 'knowledge');
    const web = webIndex >= 0 && settled[webIndex].status === 'fulfilled'
      ? settled[webIndex].value as Awaited<ReturnType<typeof searchWebReferences>>
      : null;
    const knowledge = knowledgeIndex >= 0 && settled[knowledgeIndex].status === 'fulfilled'
      ? settled[knowledgeIndex].value as Awaited<ReturnType<typeof searchKnowledgeReferences>>
      : null;
    const errors = settled.filter((result) => result.status === 'rejected').map((result) => errorMessage(result.reason));
    if (web && !web.enabled && web.message) errors.push(web.message);
    const results = [
      ...(web?.results ?? []).map(webResultToView),
      ...(knowledge?.results ?? []).map(knowledgeResultToView),
    ];
    const summary = buildReferenceSummary(intent || query, web?.results ?? [], knowledge?.results ?? []);
    if (summary) onChange(updateStageInputDefault(stageRef.current, 'reference_summary', summary));
    const allChannelsFailed = !knowledge && !web;
    setSearchState({
      status: allChannelsFailed ? 'error' : results.length ? 'success' : 'empty',
      message: searchOutcomeMessage(results.length, errors, knowledge?.message),
      results,
      retry: errors.length || !results.length ? 'smart' : null,
    });
  };

  const runKnowledgeSearch = async () => {
    const selectedTitles = knowledgeDocuments.filter((doc) => docIds.includes(doc.doc_id)).map((doc) => doc.title);
    const query = (intent || keywords.join(' ') || selectedTitles.join(' ')).trim();
    if (!query) {
      setSearchState({ status: 'error', message: '请填写检索重点、参考关键词，或选择知识库文档。', results: [], retry: null });
      return;
    }
    if (!projectId) {
      setSearchState({ status: 'error', message: '请先上传当前项目的知识库文档。', results: [], retry: null });
      return;
    }
    const requestId = ++requestRef.current;
    setSearchState({ status: 'loading', message: '正在检索已选项目资料...', results: [], retry: 'knowledge' });
    try {
      const response = await searchKnowledgeReferences({ query, intent, projectId, docIds, topK: 6 });
      if (requestId !== requestRef.current) return;
      const results = response.results.map(knowledgeResultToView);
      const summary = summarizeKnowledgeResults(response.results);
      if (summary) onChange(updateStageInputDefault(stageRef.current, 'reference_summary', summary));
      setSearchState({
        status: results.length ? 'success' : 'empty',
        message: response.message || (results.length ? `找到 ${results.length} 条项目资料。` : '没有找到相关项目资料，可调整检索重点后重试。'),
        results,
        retry: results.length ? null : 'knowledge',
      });
    } catch (error) {
      if (requestId !== requestRef.current) return;
      setSearchState({ status: 'error', message: `知识库检索失败：${errorMessage(error)}`, results: [], retry: 'knowledge' });
    }
  };

  const retry = searchState.retry === 'smart' ? runSmartSearch : runKnowledgeSearch;

  return (
    <section aria-busy={searchState.status === 'loading'} className="reference-panel brief-reference-panel">
      <div className="reference-panel-head">
        <span>{selectedMode.icon}<span>参考资料</span></span>
        <small>参考摘要只进入前置创作立项，并保留可追溯的真实来源。</small>
      </div>
      <ReferenceModeTabs activeMode={mode} idBase={tabsId} items={modes} onChange={updateMode} />

      <div aria-labelledby={`${tabsId}-tab-${mode}`} className="reference-mode-body" id={`${tabsId}-panel-${mode}`} role="tabpanel">
        {mode === 'smart_search' ? (
          <>
            <CompactTagInput label="参考关键词" value={keywords} onChange={(value) => onChange(updateStageInputDefault(stage, 'reference_keywords', value))} />
            <ReferenceIntentField intent={intent} onChange={(value) => onChange(updateStageInputDefault(stage, 'reference_query_intent', value))} />
            <label className="inline-switch reference-switch">
              <input checked={webEnabled} type="checkbox" onChange={(event) => onChange(updateStageInputDefault(stage, 'enable_web_search', event.target.checked))} />
              <span>{webEnabled ? '同时检索公开网页与项目知识库' : '仅检索项目知识库'}</span>
            </label>
            <LoadingButton className="tech-button" loading={searchState.status === 'loading'} loadingLabel="检索中" onClick={() => void runSmartSearch()}><Globe2 size={14} />生成参考摘要</LoadingButton>
          </>
        ) : null}

        {mode === 'url' ? (
          <>
            <CompactTagInput label="参考链接" placeholder="粘贴 URL 后按回车" value={urls} onChange={(value) => onChange(updateStageInputDefault(stage, 'reference_urls', value))} />
            <p className="reference-message">创作启动后提取公开页面正文；需登录或协议不允许访问的页面会明确跳过。</p>
          </>
        ) : null}

        {mode === 'knowledge_base' ? (
          <>
            <ReferenceIntentField intent={intent} onChange={(value) => onChange(updateStageInputDefault(stage, 'reference_query_intent', value))} />
            <div className="reference-knowledge-actions">
              {onOpenKnowledgeManager ? <button className="tech-button" onClick={onOpenKnowledgeManager} type="button"><Settings2 size={14} />管理知识库</button> : null}
              <LoadingButton className="ghost tiny-action" loading={searchState.status === 'loading'} loadingLabel="检索中" onClick={() => void runKnowledgeSearch()}><DatabaseZap size={13} />检索已选文档</LoadingButton>
            </div>
            <div className="knowledge-doc-list">
              {knowledgeDocuments.length ? knowledgeDocuments.map((doc) => (
                <button aria-pressed={docIds.includes(doc.doc_id)} className={docIds.includes(doc.doc_id) ? 'selected' : ''} key={doc.doc_id} onClick={() => toggleDocument(stage, docIds, doc.doc_id, onChange)} type="button">
                  <strong>{doc.title}</strong><small>{doc.chunk_count} 个片段 · 语义索引</small>
                </button>
              )) : <p className="reference-message">暂无知识库文档，请先打开知识库管理器上传资料。</p>}
            </div>
          </>
        ) : null}
      </div>

      {searchState.message ? (
        <div className={`reference-search-state ${searchState.status}`} role={searchState.status === 'error' ? 'alert' : 'status'}>
          <span>{searchState.message}</span>
          {searchState.retry ? <LoadingButton aria-label="重试参考检索" className="ghost tiny-action" loading={searchState.status === 'loading'} loadingLabel="重试中" onClick={() => void retry()}><RefreshCw size={12} />重试</LoadingButton> : null}
        </div>
      ) : null}
      {searchState.results.length ? (
        <div className="reference-results compact">
          {searchState.results.slice(0, 6).map((result) => (
            <article className="reference-result readonly" key={result.id}>
              <span><strong>{result.title || '参考资料'}</strong><small>{result.preview}</small></span>
              <div className="reference-result-meta">
                <em>{result.source === 'web' ? '公开网页' : `知识库${result.section ? ` · ${result.section}` : ''}`}</em>
                {result.url && safeHttpUrl(result.url) ? <a href={result.url} rel="noopener noreferrer" target="_blank">打开来源<ExternalLink size={11} /></a> : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ReferenceIntentField({ intent, onChange }: { intent: string; onChange: (value: string) => void }) {
  return <label className="reference-intent-field"><span>检索重点</span><textarea value={intent} onChange={(event) => onChange(event.target.value)} /></label>;
}

function CompactTagInput({ label, value, onChange, placeholder = '输入后按回车添加' }: { label: string; value: string[]; onChange: (value: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState('');
  const labelId = useId();
  const commit = () => {
    const next = addTagValue(value, draft).map(String);
    onChange(next);
    setDraft('');
  };
  return (
    <div className="compact-tag-editor"><span id={labelId}>{label}</span><div className="tag-input-box">
      <div className="tag-chip-row">{value.map((tag) => <button key={tag} onClick={() => onChange(removeTagValue(value, tag).map(String))} type="button">{tag}<X size={10} /></button>)}</div>
      <input aria-labelledby={labelId} onBlur={() => draft.trim() && commit()} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (['Enter', ',', '，', '、'].includes(event.key)) { event.preventDefault(); commit(); } }} placeholder={placeholder} value={draft} />
    </div></div>
  );
}

function fieldValue(stage: WorkflowStage, key: string) {
  return stage.input_schema.find((field) => field.key === key)?.default;
}

function asStringArray(value: unknown) {
  if (Array.isArray(value)) return value.map(String);
  if (!value) return [];
  return String(value).split(/[,\n，、]/).map((item) => item.trim()).filter(Boolean);
}

function toggleDocument(stage: WorkflowStage, ids: string[], docId: string, onChange: (stage: WorkflowStage) => void) {
  onChange(updateStageInputDefault(stage, 'knowledge_base_doc_ids', ids.includes(docId) ? ids.filter((item) => item !== docId) : [...ids, docId]));
}

function webResultToView(result: ReferenceSearchResult): ViewResult {
  return { id: `web-${result.url || result.title}`, title: result.title, preview: result.content, source: 'web', url: result.url };
}

function knowledgeResultToView(result: KnowledgeSearchResult): ViewResult {
  return { id: `knowledge-${result.chunk_id}`, title: result.title, preview: result.preview, section: result.section, source: 'knowledge' };
}

function buildReferenceSummary(intent: string, web: ReferenceSearchResult[], knowledge: KnowledgeSearchResult[]) {
  const parts = [`检索意图：${intent}`];
  if (web.length) parts.push(`公开网页\n${web.slice(0, 5).map((item, index) => `${index + 1}. ${item.title}\n${item.content}\nURL: ${item.url}`).join('\n\n')}`);
  if (knowledge.length) parts.push(`项目知识库\n${summarizeKnowledgeResults(knowledge)}`);
  return parts.length > 1 ? parts.join('\n\n') : '';
}

function summarizeKnowledgeResults(results: KnowledgeSearchResult[]) {
  return results.slice(0, 6).map((item, index) => `${index + 1}. ${item.title}${item.section ? ` / ${item.section}` : ''}\n${item.preview}`).join('\n\n');
}

function searchOutcomeMessage(count: number, errors: string[], knowledgeMessage?: string) {
  if (count && errors.length) return `已保留 ${count} 条可用结果；部分来源失败：${errors.join('；')}`;
  if (count) return `找到 ${count} 条可追溯参考。`;
  if (errors.length) return `没有取得可用结果：${errors.join('；')}`;
  return knowledgeMessage || '没有找到相关内容，可调整关键词后重试。';
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '未知错误';
}

function safeHttpUrl(value: string) {
  try {
    return ['http:', 'https:'].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}

const modes: Array<{ key: ReferenceMode; label: string; hint: string; icon: ReactNode }> = [
  { key: 'smart_search', label: '智能搜索', hint: '真实来源', icon: <Globe2 size={14} /> },
  { key: 'url', label: '指定链接', hint: '公开网页', icon: <Link2 size={14} /> },
  { key: 'knowledge_base', label: '项目资料', hint: '知识库检索', icon: <DatabaseZap size={14} /> },
];

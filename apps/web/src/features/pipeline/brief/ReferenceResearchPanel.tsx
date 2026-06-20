import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { DatabaseZap, Globe2, Link2, Settings2, UploadCloud, X } from 'lucide-react';
import type { KnowledgeDocument, WorkflowStage } from '../contracts';
import { listKnowledgeDocuments, uploadKnowledgeFile } from '../services/knowledge';
import { addTagValue, removeTagValue, updateStageInputDefault } from '../lib/stageConfig';

type ReferenceMode = 'smart_search' | 'url' | 'knowledge_base';

type SearchResult = {
  title: string;
  url?: string;
  content?: string;
  preview?: string;
  score: number;
  doc_id?: string;
  chunk_id?: string;
  section?: string;
};

type Props = {
  stage: WorkflowStage;
  onKnowledgeDocumentsChanged?: () => void;
  onOpenKnowledgeManager?: () => void;
  onChange: (stage: WorkflowStage) => void;
};

export function ReferenceResearchPanel({ stage, onChange, onKnowledgeDocumentsChanged, onOpenKnowledgeManager }: Props) {
  const mode = String(fieldValue(stage, 'reference_mode') || 'smart_search') as ReferenceMode;
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const keywords = asStringArray(fieldValue(stage, 'reference_keywords'));
  const urls = asStringArray(fieldValue(stage, 'reference_urls'));
  const docIds = asStringArray(fieldValue(stage, 'knowledge_base_doc_ids'));
  const webEnabled = Boolean(fieldValue(stage, 'enable_web_search'));
  const intent = String(fieldValue(stage, 'reference_query_intent') || '');

  useEffect(() => {
    void refreshDocuments();
  }, []);

  const selectedMode = useMemo(() => modes.find((item) => item.key === mode) ?? modes[0], [mode]);

  const updateMode = (nextMode: ReferenceMode) => {
    onChange(updateStageInputDefault(stage, 'reference_mode', nextMode));
    setResults([]);
    setMessage('');
  };

  const runSmartSearch = async () => {
    const query = keywords.join(' ');
    if (!query.trim()) {
      setMessage('请先录入 1-3 个参考关键词。');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      const mergedResults: SearchResult[] = [];
      const summaryParts: string[] = [`检索意图：${intent || query}`];
      if (webEnabled) {
        const response = await fetch('/api/references/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, max_results: 3, search_depth: 'basic' }),
        });
        const data = await response.json();
        if (data.enabled && data.results?.length) {
          mergedResults.push(...data.results);
          summaryParts.push(`联网参考（优先）\n${summarizeWebResults(data.results)}`);
        } else {
          summaryParts.push(`联网参考（优先）\n${data.message || '联网搜索暂无可用结果。'}`);
        }
      }
      const knowledge = await fetchKnowledgeResults(query);
      mergedResults.push(...knowledge.results);
      summaryParts.push(`用户知识库命中（补充）\n${summarizeKnowledgeResults(knowledge.results) || knowledge.message || '用户知识库暂无命中。'}`);
      setResults(mergedResults);
      onChange(updateStageInputDefault(stage, 'reference_summary', summaryParts.join('\n\n')));
      setMessage(webEnabled ? '已合并联网参考与用户知识库命中。' : '已使用本地知识库生成参考摘要。');
    } catch (error) {
      setMessage(`参考检索失败：${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setBusy(false);
    }
  };

  const runKnowledgeSearch = async (query = keywords.join(' ')) => {
    if (!query.trim()) {
      setMessage('请先录入参考关键词，或选择知识库文档。');
      return;
    }
    setBusy(true);
    try {
      const data = await fetchKnowledgeResults(query);
      setResults(data.results ?? []);
      const summary = summarizeKnowledgeResults(data.results ?? []);
      onChange(updateStageInputDefault(stage, 'reference_summary', summary || data.message || '知识库暂无命中'));
      setMessage(data.message || '本地知识库检索完成。');
    } finally {
      setBusy(false);
    }
  };

  const fetchKnowledgeResults = async (query: string) => {
    const response = await fetch('/api/knowledge/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, intent, doc_ids: docIds, top_k: 6 }),
    });
    return response.json();
  };

  const handleFiles = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setBusy(true);
    setMessage('正在解析并索引文件...');
    try {
      const payload = await uploadKnowledgeFile(file);
      const document = payload.document as KnowledgeDocument;
      const nextIds = Array.from(new Set([...docIds, document.doc_id]));
      onChange(updateStageInputDefault(stage, 'knowledge_base_doc_ids', nextIds));
      await refreshDocuments();
      onKnowledgeDocumentsChanged?.();
      setMessage(`已入库：${document.title}，${document.chunk_count} 个片段。${document.capability_note || ''}`);
    } catch (error) {
      setMessage(`上传失败：${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const refreshDocuments = async () => {
    setDocuments(await listKnowledgeDocuments());
  };

  const toggleDoc = (docId: string) => {
    const nextIds = docIds.includes(docId) ? docIds.filter((item) => item !== docId) : [...docIds, docId];
    onChange(updateStageInputDefault(stage, 'knowledge_base_doc_ids', nextIds));
  };

  return (
    <section className="reference-panel info-reference-panel">
      <div className="reference-panel-head">
        <span>{selectedMode.icon}<span>参考资料</span></span>
        <small>三选一：智能搜索、指定链接、上传文件/知识库。参考摘要会自动进入小说推荐阶段。</small>
      </div>
      <div className="reference-mode-tabs">
        {modes.map((item) => (
          <button className={mode === item.key ? 'active' : ''} key={item.key} onClick={() => updateMode(item.key)} type="button">
            {item.icon}<strong>{item.label}</strong><small>{item.hint}</small>
          </button>
        ))}
      </div>

      {mode === 'smart_search' ? (
        <div className="reference-mode-body">
          <CompactTagInput label="参考关键词" value={keywords} onChange={(value) => onChange(updateStageInputDefault(stage, 'reference_keywords', value))} />
          <label className="reference-intent-field">
            <span>检索意图</span>
            <textarea value={intent} onChange={(event) => onChange(updateStageInputDefault(stage, 'reference_query_intent', event.target.value))} />
          </label>
          <label className="inline-switch reference-switch">
            <input checked={webEnabled} type="checkbox" onChange={(event) => onChange(updateStageInputDefault(stage, 'enable_web_search', event.target.checked))} />
            <span>{webEnabled ? '优先联网搜索；不可用时回退知识库' : '仅使用本地知识库检索'}</span>
          </label>
          <button className="tech-button" disabled={busy} onClick={runSmartSearch} type="button"><Globe2 size={14} />{busy ? '检索中' : '智能生成参考摘要'}</button>
        </div>
      ) : null}

      {mode === 'url' ? (
        <div className="reference-mode-body">
          <CompactTagInput label="参考链接" placeholder="粘贴 URL 后按回车" value={urls} onChange={(value) => onChange(updateStageInputDefault(stage, 'reference_urls', value))} />
          <p className="reference-message">链接会在开始创作时提取公开页面正文摘要；请避免使用需登录或版权受限的内容。</p>
        </div>
      ) : null}

      {mode === 'knowledge_base' ? (
        <div className="reference-mode-body">
          <label className="reference-intent-field">
            <span>RAG 检索提示词</span>
            <textarea value={intent} onChange={(event) => onChange(updateStageInputDefault(stage, 'reference_query_intent', event.target.value))} />
          </label>
          <input accept=".txt,.md,.markdown,.html,.htm,.epub,.pdf,.docx,.pptx,.xlsx" hidden onChange={(event) => void handleFiles(event.target.files)} ref={fileRef} type="file" />
          <button className="tech-button" disabled={busy} onClick={() => fileRef.current?.click()} type="button"><UploadCloud size={14} />上传并构建知识库</button>
          {onOpenKnowledgeManager ? (
            <button className="ghost tiny-action" disabled={busy} onClick={onOpenKnowledgeManager} type="button"><Settings2 size={13} />打开知识库管理</button>
          ) : null}
          <button className="ghost tiny-action" disabled={busy} onClick={() => void runKnowledgeSearch()} type="button"><DatabaseZap size={13} />检索已选文档</button>
          <div className="knowledge-doc-list">
            {documents.length ? documents.map((doc) => (
              <button className={docIds.includes(doc.doc_id) ? 'selected' : ''} key={doc.doc_id} onClick={() => toggleDoc(doc.doc_id)} type="button">
                <strong>{doc.title}</strong>
                <small>{doc.chunk_count} chunks · {doc.parser}</small>
              </button>
            )) : <p className="reference-message">暂无知识库文档。支持 TXT/MD/HTML；安装 Docling 后可增强 PDF/DOCX/PPTX/XLSX 解析。</p>}
          </div>
        </div>
      ) : null}

      {message ? <p className="reference-message">{message}</p> : null}
      {results.length ? (
        <div className="reference-results compact">
          {results.slice(0, 4).map((result) => (
            <article className="reference-result readonly" key={result.url || result.chunk_id || result.title}>
              <span>
                <strong>{result.title || '参考资料'}</strong>
                <small>{result.content || result.preview || result.url}</small>
                {result.url ? <em><Link2 size={11} />{result.url}</em> : null}
              </span>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CompactTagInput({ label, value, onChange, placeholder = '输入后按回车添加' }: { label: string; value: string[]; onChange: (value: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState('');
  const commit = () => {
    const next = addTagValue(value, draft).map(String);
    onChange(next);
    setDraft('');
  };
  return (
    <label className="compact-tag-editor">
      <span>{label}</span>
      <div className="tag-input-box">
        <div className="tag-chip-row">
          {value.map((tag) => (
            <button key={tag} onClick={() => onChange(removeTagValue(value, tag).map(String))} type="button">{tag}<X size={10} /></button>
          ))}
        </div>
        <input
          onBlur={() => draft.trim() && commit()}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',' || event.key === '，' || event.key === '、') {
              event.preventDefault();
              commit();
            }
          }}
          placeholder={placeholder}
          value={draft}
        />
      </div>
    </label>
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

function summarizeWebResults(results: SearchResult[]) {
  return results.slice(0, 4).map((item, index) => `${index + 1}. ${item.title}\n${item.content || item.preview || ''}\nURL: ${item.url || ''}`).join('\n\n');
}

function summarizeKnowledgeResults(results: SearchResult[]) {
  return results.slice(0, 6).map((item, index) => `${index + 1}. ${item.title}${item.section ? ` / ${item.section}` : ''}\n${item.preview || item.content || ''}\nscore=${Number(item.score || 0).toFixed(2)}`).join('\n\n');
}

const modes: Array<{ key: ReferenceMode; label: string; hint: string; icon: ReactNode }> = [
  { key: 'smart_search', label: '智能搜索', hint: '关键词即可', icon: <Globe2 size={14} /> },
  { key: 'url', label: '指定链接', hint: '公开网页', icon: <Link2 size={14} /> },
  { key: 'knowledge_base', label: '上传文件 / 知识库', hint: 'RAG 检索', icon: <DatabaseZap size={14} /> },
];

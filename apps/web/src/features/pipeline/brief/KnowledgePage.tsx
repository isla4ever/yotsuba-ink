import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  Database,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import type {
  KnowledgeDocument,
  KnowledgeUploadPhase,
} from "@/features/pipeline/contracts/knowledge"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import {
  deleteKnowledgeDocument,
  knowledgeBackendLabel,
  listKnowledgeDocuments,
  uploadKnowledgeFile,
} from "@/features/pipeline/services/knowledgeApi"
import { listProjects } from "@/features/pipeline/services/projectApi"

type KnowledgeRow = KnowledgeDocument & { projectTitle: string }

export default function KnowledgePage() {
  const { activeProject, activeProjectId } = useApp()
  const [documents, setDocuments] = useState<KnowledgeRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [query, setQuery] = useState("")
  const [uploadPhase, setUploadPhase] = useState<KnowledgeUploadPhase | "">("")
  const [deletingId, setDeletingId] = useState("")
  const fileRef = useRef<HTMLInputElement>(null)
  const isProjectScope = Boolean(activeProjectId)

  const load = useCallback(
    (signal?: AbortSignal) => {
      setLoading(true)
      setError("")
      const request = activeProjectId
        ? listKnowledgeDocuments(activeProjectId, signal).then((items) =>
            items.map((item) => ({
              ...item,
              projectTitle: activeProject?.title || "当前作品",
            })),
          )
        : listProjects(signal).then(async (projects) => {
            const groups = await Promise.all(
              projects.map(async (project) => {
                try {
                  const items = await listKnowledgeDocuments(project.id, signal)
                  return items.map((item) => ({
                    ...item,
                    projectTitle: project.title,
                  }))
                } catch (reason) {
                  if (signal?.aborted) throw reason
                  return []
                }
              }),
            )
            return groups.flat()
          })
      void request
        .then(setDocuments)
        .catch((reason) => {
          if (!signal?.aborted)
            setError(
              reason instanceof Error ? reason.message : "知识库读取失败",
            )
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false)
        })
    },
    [activeProject?.title, activeProjectId],
  )

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN")
    if (!needle) return documents
    return documents.filter((item) =>
      [
        item.title,
        item.filename,
        item.preview,
        item.projectTitle,
        item.parser,
        item.backend,
      ].some((value) =>
        String(value || "")
          .toLocaleLowerCase("zh-CN")
          .includes(needle),
      ),
    )
  }, [documents, query])

  const upload = async (file?: File) => {
    if (!file || !activeProjectId || uploadPhase) return
    setError("")
    try {
      const response = await uploadKnowledgeFile(
        file,
        activeProjectId,
        setUploadPhase,
      )
      setDocuments((current) => [
        {
          ...response.document,
          projectTitle: activeProject?.title || "当前作品",
        },
        ...current.filter((item) => item.doc_id !== response.document.doc_id),
      ])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "资料上传失败")
    } finally {
      setUploadPhase("")
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  const remove = async (item: KnowledgeRow) => {
    if (
      !window.confirm(
        `确认从《${item.projectTitle}》知识库删除“${item.filename}”？`,
      )
    )
      return
    setDeletingId(item.doc_id)
    setError("")
    try {
      await deleteKnowledgeDocument(item.doc_id, item.project_id)
      setDocuments((current) =>
        current.filter((doc) => doc.doc_id !== item.doc_id),
      )
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "资料删除失败")
    } finally {
      setDeletingId("")
    }
  }

  const initialLoad = useLoadingPresence(loading && documents.length === 0)

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在索引知识资料"
        detail="同步 Source Pack 文档、解析状态与检索后端"
      />
    )
  }

  const indexedCount = documents.filter(
    (item) => item.status === "ready" || item.status === "indexed",
  ).length

  return (
    <div className="flex-1 overflow-hidden flex flex-col page-in">
      <div className="border-b border-hairline bg-surface px-4 md:px-6 py-3 flex items-center gap-3 shrink-0">
        <Database size={14} className="text-fog" />
        <span className="text-sm font-medium text-ink">
          {isProjectScope ? "本书知识库" : "知识总览"}
        </span>
        <span className="hidden sm:inline text-xs text-fog">
          · {documents.length} 个文件 · {indexedCount} 个可检索 ·{" "}
          {knowledgeBackendLabel(documents)}
        </span>
        <div className="flex-1" />
        <button
          type="button"
          className="btn btn-ghost p-1.5"
          onClick={() => load()}
          aria-label="刷新知识库"
        >
          <RefreshCw size={13} />
        </button>
        {isProjectScope && (
          <button
            type="button"
            className="btn btn-secondary text-xs"
            onClick={() => fileRef.current?.click()}
            disabled={Boolean(uploadPhase)}
          >
            {uploadPhase ? (
              <RefreshCw size={13} className="animate-spin" />
            ) : (
              <Plus size={13} />
            )}
            {uploadPhase === "reading"
              ? "读取文件"
              : uploadPhase === "indexing"
                ? "建立索引"
                : "添加文件"}
          </button>
        )}
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={(event) => void upload(event.target.files?.[0])}
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 md:px-6 py-5">
          {error && (
            <div className="banner-warning mb-4" role="alert">
              {error}
            </div>
          )}
          <div className="knowledge-search-field relative mb-5">
            <Search
              size={14}
              className="knowledge-search-icon absolute top-1/2 -translate-y-1/2 text-fog"
              aria-hidden="true"
            />
            <input
              className="input knowledge-search-input"
              type="search"
              aria-label="搜索知识库资料"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索标题、正文预览、解析器或作品…"
            />
          </div>

          <div className="space-y-2">
            {filtered.map((item) => (
              <article
                key={item.doc_id}
                className="flex items-center gap-3 bg-surface border border-hairline rounded-lg px-4 py-3 hover:bg-hover transition-colors"
              >
                <div className="w-9 h-9 rounded bg-hover flex items-center justify-center text-[10px] font-mono text-fog shrink-0 uppercase">
                  {extension(item.filename)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <strong className="text-sm text-ink font-medium truncate">
                      {item.filename}
                    </strong>
                    {!isProjectScope && (
                      <span className="badge badge-ash shrink-0">
                        {item.projectTitle}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 mt-1 text-[10px] text-fog flex-wrap">
                    <span>{item.parser || "未知解析器"}</span>
                    <span>· {item.chunk_count} 个片段</span>
                    {typeof item.char_count === "number" && (
                      <span>
                        · {item.char_count.toLocaleString("zh-CN")} 字符
                      </span>
                    )}
                    {item.preview && (
                      <span className="truncate max-w-[32rem]">
                        · {item.preview}
                      </span>
                    )}
                  </div>
                </div>
                <span
                  className={`badge ${
                    item.status === "ready" || item.status === "indexed"
                      ? "badge-mint"
                      : "badge-amber"
                  }`}
                >
                  {statusLabel(item.status)}
                </span>
                {isProjectScope && (
                  <button
                    type="button"
                    className="btn btn-ghost p-1.5 text-fog hover:text-risk"
                    onClick={() => void remove(item)}
                    disabled={deletingId === item.doc_id}
                    aria-label={`删除${item.filename}`}
                  >
                    {deletingId === item.doc_id ? (
                      <RefreshCw size={13} className="animate-spin" />
                    ) : (
                      <Trash2 size={13} />
                    )}
                  </button>
                )}
              </article>
            ))}
          </div>

          {filtered.length === 0 && (
            <div className="bg-surface border border-dashed border-hairline rounded-lg p-10 text-center">
              <FileText
                size={24}
                className="text-fog mx-auto mb-2 opacity-40"
              />
              <strong className="block text-sm text-ink mb-1">
                {query ? "没有匹配资料" : "尚未上传 Source Pack"}
              </strong>
              <span className="text-xs text-fog">
                {isProjectScope
                  ? "资料只用于 Brief、Spine 与 Volumes 的前置规划，不会盲目注入正文。"
                  : "进入具体作品后可上传并管理该书的知识资料。"}
              </span>
            </div>
          )}

          {isProjectScope && (
            <div
              className="mt-6 bg-surface border border-dashed border-hairline rounded-lg p-6 text-center"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault()
                void upload(event.dataTransfer.files?.[0])
              }}
            >
              <Upload size={22} className="text-fog mx-auto mb-2 opacity-50" />
              <p className="text-sm text-fog mb-3">拖拽单个资料文件到此处</p>
              <button
                type="button"
                className="btn btn-secondary text-xs"
                onClick={() => fileRef.current?.click()}
                disabled={Boolean(uploadPhase)}
              >
                <Plus size={13} /> 选择文件
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function extension(filename: string) {
  return filename.split(".").pop()?.slice(0, 4) || "FILE"
}

function statusLabel(status: string) {
  if (status === "ready" || status === "indexed") return "已索引"
  if (status === "failed") return "失败"
  return status || "处理中"
}

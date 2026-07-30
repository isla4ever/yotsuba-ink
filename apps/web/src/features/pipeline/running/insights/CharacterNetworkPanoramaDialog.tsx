import { lazy, Suspense, useMemo, useState } from 'react';
import { Focus, Minus, Network, Plus, X } from 'lucide-react';
import { motion } from 'motion/react';
import { createPortal } from 'react-dom';
import type { CharacterGraph, QualityMode } from '../../contracts';
import { backdropMotionVariants, dialogMotionVariants } from '../../lib/motion';
import { qualityModeColors } from '../../lib/qualityModes';
import { useOverlayDialog } from '../../state/useOverlayDialog';

const CharacterNetwork3DView = lazy(() =>
  import('../bible/CharacterNetwork3DView').then((module) => ({ default: module.CharacterNetwork3DView })),
);

type Props = {
  graph: CharacterGraph;
  mode: QualityMode;
  onClose: () => void;
};

type CameraRequest = {
  id: string;
  key: number;
  kind: 'fit' | 'focus' | 'zoom-in' | 'zoom-out';
};

export function CharacterNetworkPanoramaDialog({ graph, mode, onClose }: Props) {
  const [selectedId, setSelectedId] = useState(() => graph.nodes.find((node) => node.tier === 'protagonist')?.id ?? graph.nodes[0]?.id ?? '');
  const [cameraRequest, setCameraRequest] = useState<CameraRequest>({ id: '', key: 0, kind: 'fit' });
  const selected = graph.nodes.find((node) => node.id === selectedId) ?? null;
  const relations = useMemo(
    () => selected ? graph.edges.filter((edge) => edge.source === selected.id || edge.target === selected.id) : [],
    [graph.edges, selected],
  );
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose, open: true });
  const requestCamera = (kind: CameraRequest['kind'], id = '') => {
    setCameraRequest((current) => ({ id, key: current.key + 1, kind }));
  };

  return createPortal(
    <motion.div
      animate="animate"
      className={`character-panorama-backdrop app-overlay-backdrop mode-${mode}`}
      exit="exit"
      initial="initial"
      onClick={onClose}
      variants={backdropMotionVariants}
    >
      <motion.section
        animate="animate"
        aria-label="人物关系 3D 全景"
        aria-modal="true"
        className={`character-panorama-dialog app-dialog-surface mode-${mode}`}
        exit="exit"
        initial="initial"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
        variants={dialogMotionVariants}
      >
        <header className="character-panorama-head">
          <div>
            <p className="eyebrow">人物系统 · 空间全景</p>
            <h2><Network size={17} />人物关系网</h2>
          </div>
          <span>{graph.nodes.length} 人物 · {graph.edges.length} 关系</span>
          <div aria-label="3D 视角控制" className="character-panorama-controls" role="group">
            <button aria-label="缩小人物关系网" onClick={() => requestCamera('zoom-out')} title="缩小" type="button"><Minus size={15} /></button>
            <button aria-label="放大人物关系网" onClick={() => requestCamera('zoom-in')} title="放大" type="button"><Plus size={15} /></button>
            <button aria-label="适配全部人物" onClick={() => requestCamera('fit')} title="适配全部" type="button"><Focus size={15} /></button>
          </div>
          <button aria-label="关闭人物关系 3D 全景" className="modal-close" onClick={onClose} type="button"><X size={20} /></button>
        </header>

        <div className="character-panorama-layout">
          <div className="character-panorama-stage">
            <Suspense fallback={<p className="character-panorama-loading">正在准备人物空间…</p>}>
              <CharacterNetwork3DView
                accentColor={qualityModeColors[mode].accentStrong}
                cameraRequest={cameraRequest}
                graph={graph}
                isNodeDimmed={() => false}
                onSelectNode={(nodeId) => {
                  setSelectedId(nodeId);
                  requestCamera(nodeId ? 'focus' : 'fit', nodeId);
                }}
                selectedId={selectedId}
              />
            </Suspense>
          </div>
          <aside aria-label="人物全景索引" className="character-panorama-rail">
            <div className="character-panorama-index" role="list">
              {graph.nodes.map((node) => (
                <button
                  aria-pressed={node.id === selectedId}
                  key={node.id}
                  onClick={() => {
                    setSelectedId(node.id);
                    requestCamera('focus', node.id);
                  }}
                  type="button"
                >
                  <span>{node.name.slice(0, 1)}</span>
                  <strong>{node.name}</strong>
                  <small>{node.role}</small>
                </button>
              ))}
            </div>
            <section aria-live="polite" className="character-panorama-selection">
              {selected ? (
                <>
                  <p>当前聚焦</p>
                  <h3>{selected.name}</h3>
                  <span>{selected.role} · {selected.faction?.trim() || '未标注阵营'}</span>
                  <div>
                    {relations.length ? relations.map((edge) => {
                      const otherId = edge.source === selected.id ? edge.target : edge.source;
                      const other = graph.nodes.find((node) => node.id === otherId);
                      return <p key={`${edge.source}-${edge.target}`}><b>{other?.name ?? String(otherId)}</b><small>{edge.relation} · {Math.round(edge.strength * 100)}%</small></p>;
                    }) : <p><small>暂无已确认关系</small></p>}
                  </div>
                </>
              ) : (
                <>
                  <p>全景视角</p>
                  <h3>人物网络</h3>
                  <span>选择节点后聚焦关系与人物档案。</span>
                </>
              )}
            </section>
          </aside>
        </div>
      </motion.section>
    </motion.div>,
    document.body,
  );
}

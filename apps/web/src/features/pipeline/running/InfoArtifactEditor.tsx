import { BookOpenText, CheckCircle2, CircleAlert, X } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';
import { createPortal } from 'react-dom';
import type { QualityMode } from '../contracts';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { relationSummaryFor } from './CharacterRelationEditor';
import { InfoCharacterEditor, avatarFor } from './InfoCharacterEditor';
import type { InfoRecommendation } from './infoRecommendationModel';

type Props = {
  mode: 'worldbuilding' | 'character';
  qualityMode: QualityMode;
  recommendation: InfoRecommendation;
  readOnly?: boolean;
  onClose: () => void;
  onSave: (patch: Partial<InfoRecommendation>) => void;
};

const worldChecklist = [
  ['硬规则', '边界、禁忌与不可违背的事实'],
  ['地点与空间', '关键场域及其叙事作用'],
  ['组织与势力', '利益、行动方式与主线牵引'],
  ['禁忌与风险', '公开或触碰后会改变局势的信息'],
] as const;

export function InfoArtifactEditor({ mode, qualityMode, recommendation, readOnly = false, onClose, onSave }: Props) {
  const [initialWorldbuilding] = useState(recommendation.worldbuilding_detail);
  const [worldbuilding, setWorldbuilding] = useState(recommendation.worldbuilding_detail);
  const [initialCharacters] = useState(() => structuredClone(recommendation.characters));
  const [characters, setCharacters] = useState(() => structuredClone(recommendation.characters));
  const [initialRelationships] = useState(() => structuredClone(recommendation.relationships));
  const [relationships, setRelationships] = useState(() => structuredClone(recommendation.relationships));
  const [activeIndex, setActiveIndex] = useState(0);
  const activeCharacter = characters[Math.min(activeIndex, Math.max(0, characters.length - 1))];
  const dirty = mode === 'worldbuilding'
    ? !draftsEqual(initialWorldbuilding, worldbuilding)
    : !draftsEqual({ characters: initialCharacters, relationships: initialRelationships }, { characters, relationships });
  const validationIssue = mode === 'worldbuilding'
    ? (worldbuilding.trim() ? '' : '详细世界观不能为空')
    : characterValidationIssue(characters, relationships);
  const scopeLabel = mode === 'worldbuilding' ? '世界观当前稿' : '人物设定当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });

  const save = () => {
    if (validationIssue) return;
    if (mode === 'worldbuilding') {
      onSave({ worldbuilding_detail: worldbuilding });
      return;
    }
    const nextCharacters = characters.map((character) => ({
      ...character,
      relations: relationSummaryFor(character.name, relationships) || character.relations,
    }));
    onSave({ characters: nextCharacters, relationships });
  };

  return (
    <>
      {createPortal(
        <motion.div animate="animate" className={`info-editor-backdrop app-overlay-backdrop mode-${qualityMode}`} exit="exit" initial="initial" onClick={requestClose} variants={backdropMotionVariants}>
          <motion.section
            animate="animate"
            aria-label={editorTitle(mode, readOnly)}
            aria-modal="true"
            className={`info-editor-dialog app-dialog-surface ${mode}${readOnly ? ' readonly' : ''}`}
            exit="exit"
            initial="initial"
            onClick={(event) => event.stopPropagation()}
            ref={dialogRef}
            role="dialog"
            tabIndex={-1}
            variants={dialogMotionVariants}
          >
            <button aria-label="关闭编辑弹窗" className="modal-close" onClick={requestClose} title="关闭" type="button"><X size={22} /></button>
            <div className="info-editor-hero">
              <span><BookOpenText size={15} /></span>
              <div>
                <p className="eyebrow">{mode === 'worldbuilding' ? '世界观档案' : '人物档案'}</p>
                <h2>{editorTitle(mode, readOnly)}</h2>
                <p>{readOnly ? '当前内容来自已确认的小说信息稿。' : '修改仅保存到当前稿，确认定稿后才写入后续阶段。'}</p>
              </div>
            </div>

            {mode === 'worldbuilding' ? (
              <div className="world-editor-preservation">
                <aside aria-label="世界观内容检查项" className="world-editor-anchor-list">
                  {worldChecklist.map(([title, hint]) => <section key={title}><b>{title}</b><small>{hint}</small></section>)}
                </aside>
                <label className="world-editor-manuscript">
                  <span>详细世界观原稿</span>
                  <textarea aria-label={`${readOnly ? '预览' : '编辑'}详细世界观原稿`} readOnly={readOnly} value={worldbuilding} onChange={(event) => setWorldbuilding(event.target.value)} />
                </label>
              </div>
            ) : (
              <div className="character-dossier-editor">
                <div className="character-dossier-list">
                  {characters.map((character, index) => (
                    <button className={index === activeIndex ? 'active' : ''} key={`${character.name}-${index}`} onClick={() => setActiveIndex(index)} type="button">
                      <span>{avatarFor(character.name)}</span><strong>{character.name || `角色 ${index + 1}`}</strong><small>{character.identity || '身份待定'}</small>
                    </button>
                  ))}
                </div>
                {activeCharacter ? (
                  <InfoCharacterEditor
                    activeIndex={activeIndex}
                    character={activeCharacter}
                    characters={characters}
                    onChange={(patch) => setCharacters((current) => current.map((item, index) => index === activeIndex ? { ...item, ...patch } : item))}
                    onRelationshipsChange={setRelationships}
                    readOnly={readOnly}
                    relationships={relationships}
                  />
                ) : null}
              </div>
            )}

            {readOnly ? null : (
              <div className="info-editor-actions">
                {validationIssue ? <span className="unsaved-draft-status error" role="alert"><CircleAlert size={14} />{validationIssue}</span> : dirty ? <span className="unsaved-draft-status" role="status"><CircleAlert size={14} />未保存修改</span> : null}
                <button className="ghost" onClick={requestClose} type="button">取消</button>
                <button className="mode-primary-action" disabled={!dirty || Boolean(validationIssue)} onClick={save} type="button"><CheckCircle2 size={14} />保存到当前稿</button>
              </div>
            )}
          </motion.section>
        </motion.div>,
        document.body,
      )}
      {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={`mode-${qualityMode}`} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}

function editorTitle(mode: Props['mode'], readOnly: boolean) {
  if (mode === 'worldbuilding') return readOnly ? '预览详细世界观' : '编辑详细世界观';
  return readOnly ? '预览人物设定档案' : '编辑人物设定档案';
}

function characterValidationIssue(characters: InfoRecommendation['characters'], relationships: InfoRecommendation['relationships']) {
  if (!characters.length) return '至少需要一名人物';
  if (characters.some((character) => !character.name.trim() || !character.identity.trim() || !character.motivation.trim() || !character.relations.trim())) return '人物姓名、身份、动机和关系不能为空';
  const names = characters.map((character) => character.name.trim());
  if (new Set(names).size !== names.length) return '人物姓名不能重复';
  const knownNames = new Set(names);
  if (relationships.some((relationship) => !relationship.relation.trim() || relationship.source === relationship.target || !knownNames.has(relationship.source) || !knownNames.has(relationship.target))) return '人物关系必须引用两个不同的已有角色';
  return '';
}

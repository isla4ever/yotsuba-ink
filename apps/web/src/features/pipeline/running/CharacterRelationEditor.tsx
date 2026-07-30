import { Link2, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { CharacterRecommendation, InfoRecommendation } from './infoRecommendationModel';

type Relationship = InfoRecommendation['relationships'][number];

type Props = {
  activeCharacter: CharacterRecommendation;
  activeIndex: number;
  characters: CharacterRecommendation[];
  readOnly?: boolean;
  relationships: Relationship[];
  onRelationshipsChange: (relationships: Relationship[]) => void;
};

export function CharacterRelationEditor({
  activeCharacter,
  activeIndex,
  characters,
  readOnly = false,
  relationships,
  onRelationshipsChange,
}: Props) {
  const [draggedName, setDraggedName] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const relations = relationsFor(activeCharacter.name, relationships);
  const relationFor = (targetName: string) => relations.find((edge) => otherName(activeCharacter.name, edge) === targetName);
  const addRelation = (targetName: string) => {
    if (readOnly) return;
    if (!targetName || targetName === activeCharacter.name) return;
    if (relationFor(targetName)) return;
    onRelationshipsChange([
      ...relationships,
      { source: activeCharacter.name, target: targetName, relation: '关系待定 / 可配置', strength: 0.58 },
    ]);
  };

  const toggleRelation = (targetName: string) => {
    if (readOnly) return;
    if (!targetName || targetName === activeCharacter.name) return;
    const existing = relationFor(targetName);
    if (existing) removeRelation(existing);
    else addRelation(targetName);
  };

  const updateRelation = (edge: Relationship, patch: Partial<Relationship>) => {
    if (readOnly) return;
    onRelationshipsChange(relationships.map((item) => sameEdge(item, edge) ? { ...item, ...patch } : item));
  };

  const removeRelation = (edge: Relationship) => {
    if (readOnly) return;
    onRelationshipsChange(relationships.filter((item) => !sameEdge(item, edge)));
  };

  return (
    <section
      className={`dossier-relation-dropzone ${dragOver ? 'drag-over' : ''}${readOnly ? ' readonly' : ''}`}
      onDragLeave={() => setDragOver(false)}
      onDragOver={(event) => {
        if (readOnly) return;
        event.preventDefault();
        setDragOver(true);
        event.dataTransfer.dropEffect = 'copy';
      }}
      onDrop={(event) => {
        if (readOnly) return;
        event.preventDefault();
        setDragOver(false);
        addRelation(event.dataTransfer.getData('text/character-name') || event.dataTransfer.getData('text/plain') || draggedName);
        setDraggedName('');
      }}
    >
      <div className="dossier-relation-head">
        <span><Link2 size={14} />关联人物</span>
        <small>{readOnly ? `查看「${activeCharacter.name}」已写入后续阶段的人物关系。` : `选择已定稿人物，维护与「${activeCharacter.name}」的关系线。`}</small>
      </div>
      <div className="dossier-relation-candidates">
        {characters.map((character, index) => (
          <button
            aria-pressed={Boolean(relationFor(character.name))}
            className={index === activeIndex ? 'self' : relationFor(character.name) ? 'linked' : ''}
            disabled={readOnly && index !== activeIndex}
            draggable={!readOnly && index !== activeIndex}
            key={`${character.name}-${index}`}
            onMouseDown={() => setDraggedName(character.name)}
            onDragStart={(event) => {
              setDraggedName(character.name);
              if (readOnly) return;
              event.dataTransfer.setData('text/character-name', character.name);
              event.dataTransfer.setData('text/plain', character.name);
            }}
            onClick={() => toggleRelation(character.name)}
            type="button"
          >
            <b>{avatarFor(character.name)}</b>
            <span>{index === activeIndex ? '当前人物' : character.name}</span>
          </button>
        ))}
      </div>
      <div className="dossier-relation-list">
        {relations.length ? relations.map((edge) => {
          const targetName = otherName(activeCharacter.name, edge);
          const target = characters.find((character) => character.name === targetName);
          return (
            <article className="dossier-relation-card" key={`${edge.source}-${edge.target}`}>
              <div className="relation-card-person">
                <span>{avatarFor(targetName)}</span>
                <div>
                  <strong>{targetName}</strong>
                  <small>{target?.identity ?? '关联人物'}</small>
                </div>
              </div>
              <label className="relation-description-field">
                <small>关系描述</small>
                <input readOnly={readOnly} value={edge.relation} onChange={(event) => updateRelation(edge, { relation: event.target.value })} />
              </label>
              <label className="relation-strength-field">
                <small><span>关系强度</span><b>{Math.round(edge.strength * 100)}%</b></small>
                <input
                  max={1}
                  min={0.1}
                  onChange={(event) => updateRelation(edge, { strength: Number(event.target.value) })}
                  disabled={readOnly}
                  step={0.01}
                  type="range"
                  value={edge.strength}
                />
              </label>
              {readOnly ? null : (
                <button aria-label={`移除与 ${targetName} 的关系`} className="relation-remove-button" onClick={() => removeRelation(edge)} type="button">
                  <Trash2 size={15} />
                </button>
              )}
            </article>
          );
        }) : (
          <div className="dossier-relation-empty">从上方候选点击或拖入人物，建立与「{activeCharacter.name}」相关的关系线。</div>
        )}
      </div>
    </section>
  );
}

export function relationSummaryFor(name: string, relationships: Relationship[]) {
  return relationsFor(name, relationships)
    .map((edge) => `与${otherName(name, edge)}：${edge.relation}`)
    .join('；');
}

function relationsFor(name: string, relationships: Relationship[]) {
  return relationships.filter((edge) => edge.source === name || edge.target === name);
}

function otherName(name: string, edge: Relationship) {
  return edge.source === name ? edge.target : edge.source;
}

function sameEdge(a: Relationship, b: Relationship) {
  return (a.source === b.source && a.target === b.target) || (a.source === b.target && a.target === b.source);
}

function avatarFor(name: string) {
  return name.trim().slice(0, 1) || '人';
}

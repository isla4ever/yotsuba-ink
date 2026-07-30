import { describe, expect, it } from 'vitest';
import {
  validateDetailBlueprintDraft,
  validateDetailCharacterShiftDraft,
  validateDetailForeshadowDraft,
  validateDetailWorldWikiDraft,
} from './detailDraftValidation';
import type { DetailBaseline } from './detailArtifactModel';

const baseline: DetailBaseline = {
  characters: [{ name: '林澈', identity: '声纹修复师' }, { name: '许望舒', identity: '记者' }],
  relationships: [{ source: '林澈', target: '许望舒', relation: '调查同盟' }],
  worldAnchors: ['雾钟'],
  worldbuildingDetail: '旧港雾钟记录声纹证词。',
  foreshadows: ['父亲签章'],
};

describe('detail draft validation', () => {
  it('trims a complete chapter blueprint and rejects duplicate chapter names', () => {
    const validation = validateDetailBlueprintDraft({
      chapter: ' 第1章 ',
      pov: ' 林澈 ',
      scene: ' 档案馆 ',
      entry_state: ' 回避旧案 ',
      goal: ' 修复母带 ',
      conflict: ' 证据即将封存 ',
      stakes: ' 失去证据入口 ',
      hook: ' 母带喊出姓名 ',
      continuity_notes: ' 保持技术规则 ',
    }, baseline, ['第1章', '第1章'], 0);

    expect(validation.valid).toBe(false);
    expect(validation.errors.chapter).toContain('重复');
    expect(validation.value.scene).toBe('档案馆');
    expect(validation.value.pov).toBe('林澈');
  });

  it('requires paired relationship fields and rejects a self relation', () => {
    const missingRelation = validateDetailCharacterShiftDraft({
      character: '林澈', related_to: '许望舒', relation: '', pressure: '封存', motivation: '保住母带', change: '主动调查', impact: '进入下一章',
    }, baseline);
    expect(missingRelation.errors.relation).toBeTruthy();

    const selfRelation = validateDetailCharacterShiftDraft({
      character: '林澈', related_to: '林澈', relation: '自我怀疑', pressure: '封存', motivation: '保住母带', change: '主动调查', impact: '进入下一章',
    }, baseline);
    expect(selfRelation.errors.related_to).toContain('不能');
  });

  it('rejects duplicate facts and Wiki titles while preserving valid anchors', () => {
    const validation = validateDetailWorldWikiDraft({
      fact_reveals: [
        { anchor: '雾钟', fact: '母带存在', impact: '获得证据' },
        { anchor: '雾钟', fact: ' 母带存在 ', impact: '确认来源' },
      ],
      wiki_candidates: [
        { title: '7A-13 母带', fact: '保存证词', source_anchor: '雾钟' },
        { title: ' 7A-13 母带 ', fact: '十年前录制', source_anchor: '雾钟' },
      ],
    }, baseline);

    expect(validation.errors['fact_reveals.0.fact']).toContain('重复');
    expect(validation.errors['wiki_candidates.1.title']).toContain('重复');
    expect(validation.value.wiki_candidates[1].title).toBe('7A-13 母带');
  });

  it('requires unique, complete foreshadow ledger entries', () => {
    const validation = validateDetailForeshadowDraft([
      { name: '父亲签章', status: '投放', note: '留下来源疑问' },
      { name: ' 父亲签章 ', status: '推进', note: '' },
    ]);

    expect(validation.errors['foreshadow.0.name']).toContain('重复');
    expect(validation.errors['foreshadow.1.note']).toBeTruthy();
    expect(validation.value[1].name).toBe('父亲签章');
  });
});

import { describe, expect, it } from 'vitest';
import { characterBibleReadiness, parseCharacterBibleArtifact, type CharacterBibleArtifact } from './characterBibleArtifact';

const artifact: CharacterBibleArtifact = {
  subjects: [{
    id: 'subject-lin',
    name: '林默',
    kind: 'protagonist',
    function: '承担真相调查',
    background: '旧港公共档案修复师，曾参与事故母带的初次修复。',
    conflict_history: '她亲眼见过事故母带被替换，却因证据不足保持沉默。',
    present_stakes: '若证据失效，她会失去职业资格和追查母亲去向的最后机会。',
    temperament: '受压时先核对记录，再逼迫对方作出明确选择。',
    speech_style: '短句，少下判断，习惯复述记录中的原始措辞。',
    drive: '找到失踪母带',
    change: '接受共同记忆',
    debut: 'chapter:1',
    limits: ['不得无证据背叛同伴'],
    demand_refs: ['demand-investigator'],
  }],
  relations: [],
};

describe('CharacterBibleArtifact Phase 27', () => {
  it('accepts the exact Character Bible contract', () => {
    const parsed = parseCharacterBibleArtifact(JSON.stringify(artifact));
    expect(parsed.errors).toEqual([]);
    expect(parsed.artifact?.subjects[0].id).toBe('subject-lin');
    expect(characterBibleReadiness(parsed.artifact).ready).toBe(true);
  });

  it('rejects old or unknown fields instead of normalizing them', () => {
    const parsed = parseCharacterBibleArtifact(JSON.stringify({ ...artifact, schema_version: 2 }));
    expect(parsed.artifact).toBeNull();
    expect(parsed.errors[0]).toContain('未支持字段');
  });

  it('rejects relations outside the frozen registry', () => {
    const parsed = parseCharacterBibleArtifact(JSON.stringify({
      ...artifact,
      relations: [{ a: 'subject-lin', b: 'subject-missing', type: '盟友', pressure: '互不信任' }],
    }));
    expect(parsed.artifact).toBeNull();
    expect(parsed.errors).toContain('关系 1 引用了未登记主体');
  });

  it('rejects an unstructured or reversed first-appearance window', () => {
    const unstructured = structuredClone(artifact);
    unstructured.subjects[0].debut = '第一卷中段';
    expect(parseCharacterBibleArtifact(JSON.stringify(unstructured)).artifact).toBeNull();

    const reversed = structuredClone(artifact);
    reversed.subjects[0].debut = 'chapter:8-3';
    expect(parseCharacterBibleArtifact(JSON.stringify(reversed)).artifact).toBeNull();
  });
});

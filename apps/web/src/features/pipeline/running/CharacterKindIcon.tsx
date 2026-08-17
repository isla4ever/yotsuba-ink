import { Crown, History, Star, UserRound, Wrench } from 'lucide-react';
import type { CharacterKind } from './characterBibleArtifact';

const ICONS = {
  functional: Wrench,
  historical_record: History,
  major: Star,
  npc: UserRound,
  protagonist: Crown,
} satisfies Record<CharacterKind, typeof Crown>;

export const characterKindLabels: Record<CharacterKind, string> = {
  functional: '功能角色',
  historical_record: '历史主体',
  major: '重要配角',
  npc: 'NPC',
  protagonist: '主角',
};

export function CharacterKindIcon({ kind, size = 14 }: { kind: CharacterKind; size?: number }) {
  const Icon = ICONS[kind];
  return <span aria-hidden="true" className={`character-kind-icon kind-${kind}`}><Icon size={size} /></span>;
}

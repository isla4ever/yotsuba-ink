export type InfoWorldbuildingDigestKey = 'rules' | 'places' | 'groups' | 'risks';

const sections: Array<{
  aliases: string[];
  key: InfoWorldbuildingDigestKey;
  label: string;
}> = [
  { key: 'rules', label: '硬规则', aliases: ['硬规则', '规则'] },
  { key: 'places', label: '地点与空间', aliases: ['地点与空间', '地点', '空间'] },
  { key: 'groups', label: '组织与势力', aliases: ['组织与势力', '组织', '势力'] },
  { key: 'risks', label: '禁忌与风险', aliases: ['禁忌与风险', '禁忌', '风险'] },
];

export function infoWorldbuildingDigest(detail: string) {
  const markers = sections
    .map((section, sectionIndex) => {
      for (const alias of section.aliases) {
        const match = detail.match(new RegExp(`${escapeRegExp(alias)}[：:]`));
        if (match?.index !== undefined) {
          return { index: match.index, markerLength: match[0].length, sectionIndex };
        }
      }
      return null;
    })
    .filter(isMarker)
    .sort((left, right) => left.index - right.index);

  return sections.map(({ key, label }, sectionIndex) => {
    const marker = markers.find((item) => item.sectionIndex === sectionIndex);
    const next = marker ? markers.find((item) => item.index > marker.index) : undefined;
    const value = marker
      ? detail.slice(marker.index + marker.markerLength, next?.index ?? detail.length).replace(/\s+/g, ' ').trim()
      : '';
    return { key, label, value: value || '待补充' };
  });
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function isMarker(value: { index: number; markerLength: number; sectionIndex: number } | null): value is { index: number; markerLength: number; sectionIndex: number } {
  return Boolean(value);
}

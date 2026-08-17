import type {
  FrozenTextProviderBinding,
  GraphRunDefinition,
  ProviderStageId,
  WorkflowDefinition,
} from '../contracts';

export type FrozenBindingInventoryItem = {
  id: string;
  stageLabel: string;
  provider: string;
  model: string;
  prompt: string;
  budget: string;
  review: string;
  writeback: string;
};

const stageOrder: readonly ProviderStageId[] = [
  'brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover',
];

const writebackByStage: Record<ProviderStageId, string> = {
  brief: '确认后冻结到作品立项',
  spine: '确认后冻结到故事脊柱',
  cast: '确认后冻结到人物圣经',
  volumes: '确认后冻结到分卷架构',
  detail: '确认后冻结到章节施工图',
  text: '章节版本入库；Evidence 经 Outbox 写入 Canon / Wiki',
  cover: '封面 Brief 与选中资产分别入库',
};

export function frozenBindingInventory(
  definition: GraphRunDefinition,
  workflow: WorkflowDefinition,
): FrozenBindingInventoryItem[] {
  const labels = Object.fromEntries(workflow.nodes.map((node) => [node.id, node.label]));
  const textBindings = stageOrder.map((stageId) => textInventoryItem(
    stageId,
    labels[stageId] || stageId,
    definition.provider_bindings[stageId],
    definition.quality_mode,
  ));
  const image = definition.cover_asset_binding;
  return [
    ...textBindings,
    {
      id: 'cover-image',
      stageLabel: `${labels.cover || '封面'} · 图片生成`,
      provider: `${image.provider_profile_id} / ${image.template_id}`,
      model: image.model,
      prompt: 'cover-image-prompt · 由冻结 Cover Brief 确定性编译',
      budget: `${image.candidate_count} 个候选 · ${image.size} · ${image.quality} · ${image.timeout_seconds}s`,
      review: '资产尺寸、比例与落盘完整性校验',
      writeback: '候选资产入 AssetStore，作者选择后绑定 Cover Artifact',
    },
  ];
}

function textInventoryItem(
  stageId: ProviderStageId,
  stageLabel: string,
  binding: FrozenTextProviderBinding,
  qualityMode: GraphRunDefinition['quality_mode'],
): FrozenBindingInventoryItem {
  return {
    id: stageId,
    stageLabel,
    provider: `${binding.provider_profile_id} / ${binding.template_id}`,
    model: binding.model,
    prompt: `${binding.prompt_template_id} · ${binding.prompt_digest.slice(0, 12)}`,
    budget: `${binding.max_tokens.toLocaleString()} tokens · ${binding.timeout_seconds}s`,
    review: stageId === 'text'
      ? `连续性、人物${qualityMode === 'deep' ? '与文风' : '必审，文风建议审'}；超长整章重写`
      : '严格结构合同校验；候选 Artifact 等待阶段决策',
    writeback: writebackByStage[stageId],
  };
}

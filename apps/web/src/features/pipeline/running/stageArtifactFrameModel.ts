import type { StageType } from '../contracts';

export type StageArtifactFrame = Readonly<{
  artifact: string;
  decision: string;
  downstream: string;
  writeback: string;
}>;

/**
 * Writer-facing projections of the Phase 27 contract. The fields are static
 * explanations of the live Artifact authority, not a second source of truth.
 */
export const stageArtifactFrameByType = {
  brief: {
    artifact: '创作契约',
    decision: '承诺、规则与软长度',
    writeback: '冻结到作品底稿',
    downstream: '故事脊柱',
  },
  spine: {
    artifact: '因果脊柱',
    decision: '不可逆变化与结局兑现',
    writeback: '冻结到故事底稿',
    downstream: '人物编排、分卷架构',
  },
  cast: {
    artifact: '人物圣经',
    decision: '职责、关系、弧线与首现窗口',
    writeback: '冻结到人物档案',
    downstream: '分卷、施工图、正文',
  },
  volumes: {
    artifact: '分卷架构',
    decision: '承诺、冲突、高潮与闭合',
    writeback: '冻结到全书结构',
    downstream: '章节施工图',
  },
  detail: {
    artifact: '章节施工图',
    decision: '场景目标、转折与交接',
    writeback: '冻结到章节计划',
    downstream: '单章正文',
  },
  text: {
    artifact: '章节版本',
    decision: '接受、编辑或定向修订',
    writeback: '保存为章节版本',
    downstream: '下一章、封面、导出',
  },
  cover: {
    artifact: '封面资产',
    decision: '视觉 Brief 与正式资产',
    writeback: '绑定到作品封面',
    downstream: '导出交付',
  },
  export: {
    artifact: '交付清单',
    decision: '格式、章节版本与元数据',
    writeback: '物化为交付文件',
    downstream: '交付完成',
  },
} as const satisfies Record<StageType, StageArtifactFrame>;

import type { RunEvent } from '../features/pipeline/contracts';

/**
 * Dev-only stage preview fixtures. One coherent sample story (《旧港回声》)
 * rendered through the real event -> reducer -> stage view path so browser
 * design review sees exactly what a live run would produce.
 * Never imported by production code; see src/dev/previewMain.tsx.
 */

export const STAGE_PREVIEW_ORDER = ['brief', 'spine', 'cast', 'volumes', 'detail', 'text', 'cover', 'export'] as const;
export type StagePreviewId = (typeof STAGE_PREVIEW_ORDER)[number];

const briefArtifact = {
  title: '旧港回声',
  premise: '记忆检修员林岸在报废仓发现一盘本应销毁的记忆母带，编号却是他自己的工号。追查删除令的过程中，他发现自己最可信的那段记忆同样被人剪辑过，而接缝的另一端连着二十年前的旧港记忆实验。',
  promise: '每一章都让读者比林岸更早半步看见接缝，但真相的代价始终压在他身上：查下去，就要交出自己的过去。',
  world_rules: [
    '记忆可以被剪辑，但剪辑必然留下接缝，接缝会以既视感的方式反复发作',
    '记忆母带只此一份，任何复制行为都会烧毁原带',
    '记忆管理局有权对认定为高危的记忆执行封存，封存后不可申诉',
    '被剪辑者本人无法直接感知缺失，只能靠外部证据比对',
  ],
  theme: '当记忆不再可信时，人如何为自己的过去负责',
  ending_promise: '母带内容公开，旧港重启记忆听证；林岸赢得真相，但必须交出与母亲有关的三段记忆。',
  voice: '第三人称贴近视角，冷静克制，港口的雾、潮汐与机械低鸣贯穿全书意象。',
  length_envelope: { word_target_soft: 120000, chapter_target_soft: 36 },
};

const spineArtifact = {
  turns: [
    { id: 'turn-1', cause: '林岸在报废仓例行检修时发现未销毁的记忆母带，编号与他的工号一致', change: '他意识到反复发作的既视感不是病症，而是自己记忆里的接缝' },
    { id: 'turn-2', cause: '调阅检修记录后，删除令上的签名被确认是他本人的笔迹', change: '他不再信任自己的记忆，转而依赖档案、票据等外部证据行动' },
    { id: 'turn-3', cause: '档案员苏棠出示第二份笔迹样本，证明签名系他人摹写', change: '调查从「我做了什么」翻转为「谁借用了我」，林岸获得第一位盟友' },
    { id: 'turn-4', cause: '记忆管理局以高危记忆为由对母带启动封存程序', change: '调查从秘密进行变成与封存倒计时的公开赛跑' },
    { id: 'turn-5', cause: '母带在取证播放中烧毁一半，关键段落永久缺失', change: '唯一物证受损，林岸必须用自己发作的接缝去补全真相拼图' },
    { id: 'turn-6', cause: '真凶以保护全港稳定为名，提出用恢复记忆换取沉默', change: '林岸拒绝交易并选择公开听证，接受不可逆的记忆损失' },
  ],
  ending: '母带残段与林岸的接缝证词在听证会上互相印证，旧港记忆实验的删除链条被公开；林岸失去与母亲有关的三段记忆，但完整保留了此案的全部调查过程。',
  open_questions: ['管理局档案里还有多少份未销毁的母带', '苏棠调入档案室之前的身份记录为何是空白'],
  progress_types: ['information', 'relationship', 'external', 'internal'],
};

const castArtifact = {
  subjects: [
    { id: 'subject-1', name: '林岸', kind: 'protagonist', function: '记忆检修员，调查的发起者与代价承担者', drive: '找回被改写的那一晚，向母亲的记忆交代', change: '从只信自己的记忆，到学会依赖证据与同伴', debut: 'chapter:1', limits: ['不能直接读取他人记忆', '接缝发作时会短暂失去时间感'], demand_refs: ['demand-investigator'] },
    { id: 'subject-2', name: '苏棠', kind: 'major', function: '档案员，外部证据的守门人', drive: '弄清自己档案里那段空白的来历', change: '从谨慎自保到主动交出关键笔迹样本', debut: 'chapter:2', limits: ['无权调阅封存级档案'], demand_refs: ['demand-evidence'] },
    { id: 'subject-4', name: '沈慎', kind: 'major', function: '记忆管理局局长，秩序的捍卫者与对手', drive: '避免旧港因记忆实验旧案再度撕裂', change: '从执行封存到在听证会上承认程序不义', debut: 'chapter:3', limits: ['行动必须留下审批痕迹'], demand_refs: ['demand-antagonist'] },
    { id: 'subject-3', name: '老周', kind: 'functional', function: '报废仓管理员，物证链的第一环', drive: '守住仓里每一件没人认领的旧物', change: '从置身事外到替林岸保下半盘母带', debut: 'chapter:1', limits: ['夜班后记不清白天的事'], demand_refs: ['demand-witness'] },
    { id: 'subject-5', name: '阿槐', kind: 'npc', function: '码头茶摊主，街谈巷议的集散地', drive: '让茶摊在风声鹤唳的港区继续开下去', change: '无重大变化，提供舆论温度计', debut: 'chapter:1', limits: ['只转述，不作证'], demand_refs: ['demand-rumor'] },
    { id: 'subject-6', name: '林秋蘅', kind: 'historical_record', function: '林岸之母，二十年前记忆实验的受试者', drive: '（历史记录）曾试图公开实验名单', change: '（历史记录）事故身亡，记录被分段封存', debut: 'chapter:4', limits: ['仅存在于母带与档案中'], demand_refs: ['demand-history'] },
  ],
  relations: [
    { a: 'subject-1', b: 'subject-2', type: '协作', pressure: '彼此都对对方隐瞒了来历，信任随证据一页页建立' },
    { a: 'subject-1', b: 'subject-4', type: '对抗', pressure: '封存倒计时逼迫双方在程序内外互相试探' },
    { a: 'subject-1', b: 'subject-6', type: '血缘', pressure: '每接近真相一步，就要多交出一段与她有关的记忆' },
    { a: 'subject-2', b: 'subject-4', type: '上下级', pressure: '档案权限是苏棠的武器，也是沈慎的缰绳' },
    { a: 'subject-3', b: 'subject-1', type: '互信', pressure: '老周护住物证的代价是自己的值班记录出现漏洞' },
  ],
};

const volumesArtifact = {
  volumes: [
    { id: 'volume-1', promise: '林岸发现母带并确认自己被改写，把私人疑心变成一桩可以立案的旧案', conflict: '个人记忆与官方记录的正面矛盾：签名是他的，记忆却不是', climax: '第二份笔迹样本证实删除令签名系摹写，「我做了什么」翻转为「谁借用了我」', closure: '林岸以当事人身份公开申请记忆听证，调查走出阴影', turn_refs: ['turn-1', 'turn-2', 'turn-3'], cast_ids: ['subject-1', 'subject-2', 'subject-3', 'subject-5'], thread_ids: ['thread-mother-tape'], length_hint: 'medium' },
    { id: 'volume-2', promise: '与封存程序赛跑，用受损的母带和自己的接缝把真相带到听证会', conflict: '程序正义与真相的赛跑：封存合法，公开有罪', climax: '真凶提出用恢复记忆交换沉默，林岸当场拒绝并公开残带', closure: '听证会采信接缝证词，删除链条曝光，林岸接受记忆损失', turn_refs: ['turn-4', 'turn-5', 'turn-6'], cast_ids: ['subject-1', 'subject-2', 'subject-4', 'subject-6'], thread_ids: ['thread-mother-tape', 'thread-hearing'], length_hint: 'medium' },
  ],
};

const detailArtifact = {
  chapters: [
    {
      ref: 'chapter-1', volume_ref: 'volume-1', purpose: '让林岸在最日常的例行检修里撞见不该存在的母带，用他的专业冷静反衬发现的异常', pov: 'subject-1', cast_ids: ['subject-1', 'subject-3', 'subject-5'],
      scenes: [
        { place: '报废仓 B 区流水线', objective: '完成本月报废母带的例行消磁', conflict: '一盘母带的销毁回执缺失，老周坚持没有经手', turn: '母带侧标上的编号是林岸自己的工号', result: '林岸私自扣下母带，第一次违反操作规程' },
        { place: '码头茶摊', objective: '向阿槐打听最近管理局的风声', conflict: '阿槐只肯用玩笑话转述，真假掺半', turn: '一句玩笑提到「二十年前也烧过一批带子」', result: '林岸把母带藏进工具柜夹层，决定先查销毁记录' },
      ],
      handoff: '母带编号与林岸工号一致这一事实尚无解释；他明早要以检修名义调阅销毁记录。',
    },
    {
      ref: 'chapter-2', volume_ref: 'volume-1', purpose: '引入苏棠与档案室，让删除令签名把嫌疑指向林岸本人', pov: 'subject-1', cast_ids: ['subject-1', 'subject-2'],
      scenes: [
        { place: '档案室借阅窗口', objective: '调出该母带的销毁审批链', conflict: '苏棠依规拒绝出示审批人信息', turn: '林岸出示工号后，苏棠的态度从公事公办变成惊疑', result: '苏棠破例调出删除令：签名栏是林岸的笔迹' },
        { place: '档案室后廊', objective: '林岸自证清白，回忆签署当日行踪', conflict: '他对那一天的记忆流畅完整，却与考勤记录冲突', turn: '苏棠指出流畅本身就可疑——被剪辑的记忆没有犹豫', result: '两人达成脆弱同盟：各自暗中取证，互不追问动机' },
      ],
      handoff: '删除令签名待鉴定；苏棠答应三天内找到可对比的笔迹样本。',
    },
    {
      ref: 'chapter-3', volume_ref: 'volume-1', purpose: '让管理局正面入场，沈慎的合规压力收紧调查空间', pov: 'subject-1', cast_ids: ['subject-1', 'subject-4', 'subject-3'],
      scenes: [
        { place: '管理局约谈室', objective: '应付一次以流程自查为名的约谈', conflict: '沈慎句句合规，却句句都指向报废仓的缺失回执', turn: '沈慎示意约谈记录仪已关闭，问他「带子在哪」', result: '林岸咬死不知情，约谈不欢而散，监视从此贴身' },
        { place: '报废仓夜班', objective: '把母带转移出工具柜', conflict: '老周的值班记录被临时调岗打乱', turn: '老周主动把母带藏进报废的消磁机腔体', result: '物证暂时安全，老周成为链条上最脆弱的一环' },
      ],
      handoff: '监视已经贴身，母带藏在消磁机腔体；笔迹样本鉴定结果将在下一章揭晓。',
    },
    {
      ref: 'chapter-4', volume_ref: 'volume-1', purpose: '交付第一卷的翻转：签名系摹写，同时用林秋蘅的档案把旧案接进主线', pov: 'subject-2', cast_ids: ['subject-2', 'subject-1', 'subject-6'],
      scenes: [
        { place: '档案室鉴定台', objective: '完成两份笔迹的重叠比对', conflict: '比对需要封存级样本，苏棠权限不足', turn: '她动用了自己档案里那段空白期的旧凭证', result: '摹写实锤；而凭证暴露她与旧港实验的关联' },
        { place: '缩微胶片阅览间', objective: '按摹写者线索追一份二十年前的人事卷', conflict: '关键页被抽走，只剩借阅登记', turn: '登记簿上出现林秋蘅的名字——林岸的母亲', result: '旧案与母带正式接轨，林岸决定公开申请听证' },
      ],
      handoff: '林岸将以当事人身份申请记忆听证；苏棠的空白档案成为新的未爆点。',
    },
  ],
};

const chapterArtifact = {
  chapter_id: 'chapter-1',
  version_id: 'chapter-1-v2',
  title: '第一章 报废仓的低鸣',
  author_status: 'candidate',
  content: [
    '消磁机的低鸣在报废仓 B 区来回撞了二十年，撞出一种近似安静的东西。林岸对这种声音的信任，超过对自己手表的信任——手表会停，低鸣不会。',
    '十一月的第一批报废母带在传送带上排成一列，像一排等待火化的旧棺。他逐一核对侧标、扫码、按下消磁钮，动作准确得不需要经过大脑。这正是他喜欢这份工作的原因：在旧港，只有报废仓里的东西不再说谎。',
    '第三十七盘带子让流水线停了下来。',
    '销毁回执缺失。系统提示的红字很平静，林岸的手指却在扫码枪上停了两秒。他把带子翻过来，侧标上的编号先是让他觉得眼熟，随后让他觉得冷——LA-0417。他自己的工号。',
    '「老周，」他朝值班间喊，声音听起来还算正常，「三十七号带子，你经手的？」',
    '老周从值班间探出半个身子，眯眼看了看，摇头的幅度大得像要把整个问题从肩膀上抖下去。「没见过。这批单子上就没有三十七号。」',
    '林岸又看了一眼那行编号。既视感在这时候准时发作——太阳穴后面某个位置轻轻一跳，像放映机走带时跳过了一格。医生管这个叫神经性既视感，让他少喝咖啡。',
    '他把母带从传送带上取下来，塞进工具柜最底层的夹层里。做完这一切他才意识到，自己刚刚违反了入职以来遵守了九年的操作规程，而心跳居然没有变快。',
    '仿佛有什么东西比他更早做了这个决定。',
  ].join('\n\n'),
};

const coverArtifact = {
  brief: {
    concept: '夜雾中的旧港码头，一盘烧蚀过半的记忆母带悬在光束里，磁带如潮水般垂落展开成城市轮廓',
    image_prompt: 'a half-burned analog memory tape reel suspended in a cone of light over a foggy harbor at night, unspooling magnetic ribbon dissolving into a coastal city skyline, cinematic chiaroscuro, deep blue and amber palette, grainy atmosphere, no text',
    palette: ['#0d1b2a', '#1b263b', '#415a77', '#e0a458'],
    negative_constraints: ['不要出现任何文字或标志', '不要人脸特写', '避免科幻感过强的霓虹紫'],
  },
  selected_asset_id: '',
};

const exportArtifact = {
  format: 'md',
  chapter_version_ids: ['chapter-1-v2', 'chapter-2-v1', 'chapter-3-v1', 'chapter-4-v1'],
  cover_asset_id: '',
  metadata: { title: '旧港回声', author: '四叶墨', version_note: '第一卷试读装（chapter-1 ~ chapter-4）' },
};

const STAGE_ARTIFACTS: Record<StagePreviewId, Record<string, unknown>> = {
  brief: briefArtifact,
  spine: spineArtifact,
  cast: castArtifact,
  volumes: volumesArtifact,
  detail: detailArtifact,
  text: chapterArtifact,
  cover: coverArtifact,
  export: exportArtifact,
};

export type StagePreviewPhase = 'streaming' | 'candidate' | 'committed';

/** Newest-first event list, matching the run reducer's ordering convention. */
export function stagePreviewEvents(stageId: StagePreviewId, phase: StagePreviewPhase = 'candidate'): RunEvent[] {
  const runId = 'preview-run';
  let sequence = 1;
  const events: RunEvent[] = [];
  const push = (type: string, overrides: Partial<RunEvent> = {}) => {
    sequence += 1;
    events.unshift({
      event_id: `${runId}:event:${sequence}`,
      sequence,
      occurred_at: new Date(Date.UTC(2026, 7, 13, 0, 0, sequence)).toISOString(),
      run_id: runId,
      thread_id: runId,
      type,
      stage_id: null,
      node_id: '',
      chapter_id: '',
      status: '',
      payload: null,
      payload_ref: '',
      checkpoint_id: '',
      ...overrides,
    });
  };

  push('run.started');
  const stageIndex = STAGE_PREVIEW_ORDER.indexOf(stageId);
  STAGE_PREVIEW_ORDER.slice(0, stageIndex).forEach((upstream) => {
    const chapterId = upstream === 'text' ? 'chapter-1' : '';
    push('node.started', { stage_id: upstream, node_id: `${upstream}.generate_candidate`, chapter_id: chapterId });
    push('artifact.committed', { stage_id: upstream, node_id: `${upstream}.commit`, payload: STAGE_ARTIFACTS[upstream], chapter_id: chapterId });
    push('node.completed', { stage_id: upstream, node_id: `${upstream}.checkpoint_stage`, chapter_id: chapterId });
  });

  const chapterId = stageId === 'text' ? 'chapter-1' : '';
  push('node.started', { stage_id: stageId, node_id: `${stageId}.assemble_context`, chapter_id: chapterId });
  push('node.started', { stage_id: stageId, node_id: stageId === 'text' ? 'text.generate_prose' : `${stageId}.generate_candidate`, chapter_id: chapterId });
  if (phase === 'streaming') return events;

  push('artifact.candidate_ready', { stage_id: stageId, node_id: `${stageId}.generate_candidate`, payload: STAGE_ARTIFACTS[stageId], chapter_id: chapterId });
  if (stageId === 'cover') {
    push('cover.asset_ready', { stage_id: 'cover', node_id: 'cover.generate_assets', payload_ref: 'cover-asset-1' });
    push('cover.asset_ready', { stage_id: 'cover', node_id: 'cover.generate_assets', payload_ref: 'cover-asset-2' });
  }
  if (phase === 'committed') {
    push('artifact.committed', { stage_id: stageId, node_id: `${stageId}.commit`, payload: STAGE_ARTIFACTS[stageId], chapter_id: chapterId });
    push('node.completed', { stage_id: stageId, node_id: `${stageId}.checkpoint_stage`, chapter_id: chapterId });
    return events;
  }

  push('decision.required', { stage_id: stageId, node_id: `${stageId}.await_decision`, chapter_id: chapterId, payload: { reason: 'stage_decision' } });
  return events;
}

/**
 * Story Bible preview: all eight stages committed plus the continuity events
 * (evidence proposals + wiki writeback transactions) that feed the
 * foreshadow ledger and canon-facts sections.
 */
export function biblePreviewEvents(): RunEvent[] {
  const base = stagePreviewEvents('export', 'committed');
  let sequence = (base[0]?.sequence ?? 1) + 1;
  const extra: RunEvent[] = [];
  const push = (type: string, overrides: Partial<RunEvent> = {}) => {
    sequence += 1;
    extra.unshift({
      event_id: `preview-run:event:${sequence}`,
      sequence,
      occurred_at: new Date(Date.UTC(2026, 7, 13, 1, 0, sequence)).toISOString(),
      run_id: 'preview-run',
      thread_id: 'preview-run',
      type,
      stage_id: null,
      node_id: '',
      chapter_id: '',
      status: '',
      payload: null,
      payload_ref: '',
      checkpoint_id: '',
      ...overrides,
    });
  };

  push('evidence.proposed', { stage_id: 'text', chapter_id: 'chapter-1', payload: { kind: 'foreshadow', subject_ref: '母带编号 LA-0417', claim: '应销毁母带的编号与林岸工号一致，成因尚未解释' }, payload_ref: 'evidence-1' });
  push('evidence.proposed', { stage_id: 'text', chapter_id: 'chapter-2', payload: { kind: 'foreshadow', subject_ref: '删除令签名', claim: '签名笔迹与林岸一致但考勤冲突，待笔迹鉴定' }, payload_ref: 'evidence-2' });
  push('evidence.proposed', { stage_id: 'text', chapter_id: 'chapter-4', payload: { kind: 'foreshadow', subject_ref: '苏棠的空白档案', claim: '苏棠调档凭证暴露其与旧港实验的关联，来历未揭' }, payload_ref: 'evidence-3' });
  push('writeback.queued', { stage_id: 'text', chapter_id: 'chapter-4', payload: { transaction_id: 'txn-canon-chapter-4', evidence_count: 2 }, payload_ref: 'txn-canon-chapter-4' });
  push('writeback.committed', { stage_id: 'text', chapter_id: 'chapter-1', payload: { transaction_id: 'txn-canon-chapter-1', evidence_count: 3 }, payload_ref: 'txn-canon-chapter-1' });
  push('writeback.committed', { stage_id: 'text', chapter_id: 'chapter-2', payload: { transaction_id: 'txn-canon-chapter-2', evidence_count: 1 }, payload_ref: 'txn-canon-chapter-2' });
  return [...extra, ...base];
}

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { CharacterGraph } from '../../contracts';

// Records whether/when the 3D package module is actually evaluated, and captures the props handed to it.
const forceGraph3D = vi.hoisted(() => ({ loads: 0, props: null as Record<string, any> | null }));
vi.mock('react-force-graph-3d', () => {
  forceGraph3D.loads += 1;
  return {
    default: (props: Record<string, unknown>) => {
      forceGraph3D.props = props;
      return null;
    },
  };
});
// force-graph 2d requires a browser window at module scope; CharactersSection imports it statically.
vi.mock('react-force-graph-2d', () => ({ default: () => null }));

const graph: CharacterGraph = {
  nodes: [
    { id: 'p1', name: '沈默', role: '主角', faction: '调查组', faction_id: 'faction-调查组', status: '', tier: 'protagonist', first_appearance_stage: 'text', first_appearance_chapter: '1' },
    { id: 'm1', name: '林岚', role: '搭档', faction: '黑市', faction_id: 'faction-黑市', status: '', tier: 'major', first_appearance_stage: 'text', first_appearance_chapter: '1' },
    { id: 'n1', name: '摊贩', role: '线人', faction: '', status: '', tier: 'npc', first_appearance_stage: 'text', first_appearance_chapter: '2' },
  ],
  edges: [
    { source: 'p1', target: 'm1', relation: '搭档', strength: 0.8, kind: 'ally', polarity: 'positive', valid_from_stage: 'cast' },
    { source: 'n1', target: 'p1', relation: '递情报', strength: 0.3, kind: 'trade', valid_from_stage: 'text', valid_from_chapter: '2' },
  ],
  updated_by: 'test',
};

const modeAccent = '#a778ff';

describe('CharacterNetwork3DView lazy boundary', () => {
  it('is not evaluated when the 2D characters section module loads', async () => {
    await import('./CharactersSection');
    expect(forceGraph3D.loads).toBe(0);
  }, 15_000);

  it('loads the 3D package only through the dedicated view module', async () => {
    await import('./CharacterNetwork3DView');
    expect(forceGraph3D.loads).toBe(1);
  });
});

describe('CharacterNetwork3DView data mapping', () => {
  async function render(selectedId = '', dimmedId = '', onSelectNode = () => {}, showRelationshipLabels = true) {
    const { CharacterNetwork3DView } = await import('./CharacterNetwork3DView');
    renderToStaticMarkup(
      <CharacterNetwork3DView
        accentColor={modeAccent}
        graph={graph}
        isNodeDimmed={(node) => Boolean(dimmedId) && node.faction_id === dimmedId}
        onSelectNode={onSelectNode}
        selectedId={selectedId}
        showRelationshipLabels={showRelationshipLabels}
      />,
    );
    const props = forceGraph3D.props;
    if (!props) throw new Error('ForceGraph3D mock did not receive props');
    return props;
  }

  it('maps tier to node size and uses the active mode color for affiliated nodes', async () => {
    const props = await render();
    const nodes = props.graphData.nodes as Array<Record<string, any>>;
    const byId = (id: string) => nodes.find((node) => node.id === id)!;
    expect(byId('p1').val).toBeGreaterThan(byId('n1').val);
    expect(props.nodeColor(byId('p1'))).toBe(modeAccent);
    expect(props.nodeColor(byId('n1'))).toBe(modeAccent);
  });

  it('keeps projected subject kinds visually distinct instead of reducing every node to one crystal', async () => {
    const { characterNodeVisualKind } = await import('./characterNetwork3DObjects');
    expect(characterNodeVisualKind({ status: 'protagonist', tier: 'protagonist' })).toBe('protagonist');
    expect(characterNodeVisualKind({ status: 'functional', tier: 'supporting' })).toBe('functional');
    expect(characterNodeVisualKind({ status: 'historical_record', tier: 'npc' })).toBe('historical_record');
    expect(characterNodeVisualKind({ status: '', tier: 'npc' })).toBe('npc');
  });

  it('dims nodes outside the highlighted faction and keeps edges on the active mode color', async () => {
    const props = await render('', 'faction-黑市');
    const nodes = props.graphData.nodes as Array<Record<string, any>>;
    expect(props.nodeColor(nodes.find((node) => node.id === 'm1'))).toBe('#3a4152');
    const links = props.graphData.links as Array<Record<string, any>>;
    expect(props.linkColor(links[0])).toBe(modeAccent);
    expect(props.linkColor(links[1])).toBe(modeAccent);
  });

  it('keeps the performance contract while preserving direct node interaction', async () => {
    const onSelectNode = vi.fn();
    const props = await render('', '', onSelectNode);
    expect(props.cooldownTicks).toBe(120);
    expect(props.warmupTicks).toBe(42);
    expect(props.linkDirectionalParticles).toBe(0);
    expect(props.linkDirectionalArrowLength).toBe(4.2);
    expect(props.linkThreeObjectExtend).toBe(true);
    expect(props.linkThreeObject).toEqual(expect.any(Function));
    expect(props.linkCurvature).toEqual(expect.any(Function));
    expect(props.linkCurveRotation).toEqual(expect.any(Function));
    expect(props.enableNodeDrag).toBe(true);
    expect(props.nodeThreeObject).toEqual(expect.any(Function));
    expect(props.nodeThreeObjectExtend).toBe(true);
    expect(props.nodeOpacity).toBe(0);
    expect(props.nodeRelSize).toBe(7);
    props.onNodeClick((props.graphData.nodes as Array<Record<string, any>>)[1]);
    expect(onSelectNode).toHaveBeenCalledWith('m1');
  });

  it('can keep relationship lines while omitting scene labels in the stage star map', async () => {
    const props = await render('', '', () => {}, false);

    expect(props.linkThreeObjectExtend).toBe(false);
    expect(props.linkThreeObject).toBeUndefined();
    expect(props.linkPositionUpdate).toBeUndefined();
    expect(props.linkWidth).toEqual(expect.any(Function));
  });

  it('keeps the interactive panorama exposed to assistive technology', async () => {
    const { CharacterNetwork3DView } = await import('./CharacterNetwork3DView');
    const markup = renderToStaticMarkup(
      <CharacterNetwork3DView
        accentColor={modeAccent}
        graph={graph}
        isNodeDimmed={() => false}
        onSelectNode={() => {}}
        selectedId=""
      />,
    );
    expect(markup).toContain('aria-label="人物关系 3D 全景画布"');
    expect(markup).not.toContain('aria-hidden="true"');
  });

  it('starts from a legible spatial spread before the force engine settles', async () => {
    const props = await render();
    const nodes = props.graphData.nodes as Array<Record<string, number | string>>;
    const protagonist = nodes.find((node) => node.id === 'p1')!;
    const peripheral = nodes.filter((node) => node.id !== 'p1');
    expect([protagonist.x, protagonist.y, protagonist.z]).toEqual([0, 0, 0]);
    expect(new Set(peripheral.map((node) => `${node.x}:${node.y}:${node.z}`)).size).toBe(peripheral.length);
  });

  it('uses a narrower, taller spatial spread for portrait canvases', async () => {
    const { initialSpatialLayout } = await import('./CharacterNetwork3DView');
    const landscape = initialSpatialLayout(graph.nodes);
    const portrait = initialSpatialLayout(graph.nodes, 'portrait');
    expect(Math.abs(portrait[2].x ?? 0)).toBeLessThan(Math.abs(landscape[2].x ?? 0));
    expect(Math.abs(portrait[1].y ?? 0)).toBeGreaterThan(Math.abs(landscape[1].y ?? 0));
    expect(Math.abs(portrait[2].z ?? 0)).toBeLessThan(Math.abs(landscape[2].z ?? 0));
  });

  it('fits small and large networks without collapsing the camera distance', async () => {
    const { networkCameraBounds, networkCameraDistance } = await import('./CharacterNetwork3DView');
    const small = networkCameraDistance([{ ...graph.nodes[0], val: 5, x: 0, y: 0, z: 0 }], 840, 616);
    const spread = networkCameraDistance([
      { ...graph.nodes[0], val: 5, x: -360, y: 0, z: -80 },
      { ...graph.nodes[1], val: 4, x: 360, y: 220, z: 80 },
    ], 840, 616);
    expect(small).toBeGreaterThanOrEqual(228);
    expect(spread).toBeGreaterThan(small);
    expect(networkCameraBounds(spread)).toEqual({
      maximum: spread * 2.4,
      minimum: spread * 0.52,
    });
  });

  it('centers an off-axis network instead of aiming the fit camera at the world origin', async () => {
    const { networkCameraFrame } = await import('./CharacterNetwork3DView');
    const frame = networkCameraFrame([
      { ...graph.nodes[0], val: 5, x: 120, y: -80, z: 10 },
      { ...graph.nodes[1], val: 4, x: 520, y: 220, z: 90 },
    ], 840, 550);
    expect(frame.target).toEqual({ x: 320, y: 70, z: 50 });
    expect(frame.distance).toBeGreaterThanOrEqual(244);
  });
});

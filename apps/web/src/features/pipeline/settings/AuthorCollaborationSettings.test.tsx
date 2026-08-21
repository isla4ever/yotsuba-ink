// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { CollaborationSettingsEnvelope } from "../contracts/authorCollaboration"
import { AuthorCollaborationSettings } from "./AuthorCollaborationSettings"

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  save: vi.fn(),
}));

vi.mock('../services/authorCollaborationApi', () => ({
  getCollaborationSettings: mocks.get,
  saveCollaborationSettings: mocks.save,
}));

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;

describe('AuthorCollaborationSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.get.mockResolvedValue(envelope());
    mocks.save.mockReturnValue(new Promise(() => undefined));
  });

  it('switches the real Provider/model tuple submitted for future threads', async () => {
    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<AuthorCollaborationSettings />))
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });

    const select = container.querySelector<HTMLSelectElement>('select');
    expect(select).not.toBeNull();
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set?.call(
        select,
        JSON.stringify(['provider-b', 'model-b']),
      );
      select?.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const save = Array.from(container.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent?.includes('保存作者协作设置'));
    act(() => save?.click());

    expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      default_provider_profile_id: 'provider-b',
      default_model: 'model-b',
    }));
    act(() => root.unmount());
  });

  it('preserves an unavailable saved binding until the author selects a ready replacement', async () => {
    mocks.get.mockResolvedValue(unavailableEnvelope());
    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<AuthorCollaborationSettings />))
    await act(async () => {
      await Promise.resolve();
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });

    const select = container.querySelector<HTMLSelectElement>('select');
    const save = Array.from(container.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent?.includes('保存作者协作设置'));
    expect(select?.value).toBe(JSON.stringify(['provider-stale', 'model-stale']));
    expect(select?.textContent).toContain('当前绑定不可用');
    expect(container.textContent).toContain('既有线程仍保持冻结绑定');
    expect(save?.disabled).toBe(true);

    act(() => {
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set?.call(
        select,
        JSON.stringify(['provider-b', 'model-b']),
      );
      select?.dispatchEvent(new Event('change', { bubbles: true }));
    });
    expect(save?.disabled).toBe(false);
    act(() => save?.click());
    expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      default_provider_profile_id: 'provider-b',
      default_model: 'model-b',
    }));
    act(() => root.unmount());
  });

  it('keeps the settings surface recoverable when the initial request fails', async () => {
    mocks.get
      .mockRejectedValueOnce(new Error('settings endpoint unavailable'))
      .mockResolvedValueOnce(envelope());
    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<AuthorCollaborationSettings />));
    await settle();

    expect(container.textContent).toContain('无法读取作者协作设置');
    expect(container.textContent).toContain('settings endpoint unavailable');
    const retry = Array.from(container.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent?.includes('重试'));
    expect(retry).toBeDefined();
    act(() => retry?.click());
    await settle();

    expect(container.textContent).toContain('保存作者协作设置');
    expect(container.textContent).not.toContain('无法读取作者协作设置');
    act(() => root.unmount());
  });

  it('preserves the editable draft and exposes the API error when save fails', async () => {
    mocks.save.mockRejectedValueOnce(new Error('save rejected'));
    const container = document.createElement('div');
    const root = createRoot(container);
    act(() => root.render(<AuthorCollaborationSettings />));
    await settle();

    const preference = container.querySelector<HTMLTextAreaElement>(
      'textarea[placeholder^="例如：克制叙述"]',
    );
    expect(preference).not.toBeNull();
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set?.call(
        preference,
        '保留失败前的作者偏好',
      );
      preference?.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const save = Array.from(container.querySelectorAll<HTMLButtonElement>('button'))
      .find((button) => button.textContent?.includes('保存作者协作设置'));
    act(() => save?.click());
    await settle();

    expect(container.textContent).toContain('save rejected');
    expect(preference?.value).toBe('保留失败前的作者偏好');
    expect(save?.disabled).toBe(false);
    act(() => root.unmount());
  });
});

async function settle() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => window.setTimeout(resolve, 0));
  });
}

function envelope(): CollaborationSettingsEnvelope {
  return {
    settings: {
      default_mode: 'discuss',
      default_provider_profile_id: 'provider-a',
      default_model: 'model-a',
      context_policy: {
        policy_id: 'collaboration-default-v1',
        version: 1,
        max_input_chars: 24_000,
        max_history_turns: 8,
        include_author_preferences: true,
        include_craft_mechanisms: true,
        include_knowledge: false,
        include_canon_wiki: true,
        include_foreshadow: true,
        author_preferences: '',
        craft_mechanisms: [],
        source_pack_refs: [],
      },
      history_retention_days: 180,
    },
    capabilities: [
      capability('provider-a', 'model-a'),
      capability('provider-b', 'model-b'),
    ],
  };
}

function capability(provider_profile_id: string, model: string) {
  return {
    provider_profile_id,
    provider_name: provider_profile_id,
    model,
    supports_multi_turn: true,
    supports_streaming: false,
    supports_structured_patch: true,
    max_context_tokens: null,
    capability_checked_at: '2026-08-21T00:00:00Z',
    capability_source: 'discovered' as const,
    ready: true,
    issue_codes: [],
  };
}

function unavailableEnvelope(): CollaborationSettingsEnvelope {
  const record = envelope();
  return {
    settings: {
      ...record.settings,
      default_provider_profile_id: 'provider-stale',
      default_model: 'model-stale',
    },
    capabilities: [
      {
        ...capability('provider-stale', 'model-stale'),
        ready: false,
        issue_codes: ['missing_secret'],
      },
      capability('provider-b', 'model-b'),
    ],
  };
}

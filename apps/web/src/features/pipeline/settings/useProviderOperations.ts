import { useRef, useState } from 'react';
import type { ProviderProfile } from '../contracts';
import { deleteProviderProfile, discoverProviderModels, saveProviderProfile, saveProviderSecret, setDefaultProviderProfile, testProviderConnection } from '../services/providerApi';

export type ProviderOperationStatus = {
  type: 'idle' | 'saving' | 'testing' | 'discovering' | 'deleting' | 'ok' | 'error';
  message: string;
  code?: string;
};

type Options = {
  onOperationSucceeded?: () => void;
  onProviderCreated?: (provider: ProviderProfile) => void;
  onProviderDeleted?: (providerId: string) => void;
  onProvidersUpdated?: (providers: ProviderProfile[]) => void;
  onProviderUpdated: (provider: ProviderProfile) => void;
};

export class ProviderOperationGate {
  private active = new Set<string>();

  isActive(providerId: string) {
    return this.active.has(providerId);
  }

  async run(providerId: string, operation: () => Promise<void>) {
    if (this.active.has(providerId)) return false;
    this.active.add(providerId);
    try {
      await operation();
      return true;
    } finally {
      this.active.delete(providerId);
    }
  }
}

export function useProviderOperations({ onOperationSucceeded, onProviderCreated, onProviderDeleted, onProvidersUpdated, onProviderUpdated }: Options) {
  const [secretInputs, setSecretInputs] = useState<Record<string, string>>({});
  const [statuses, setStatuses] = useState<Record<string, ProviderOperationStatus>>({});
  const gateRef = useRef(new ProviderOperationGate());
  const onProviderUpdatedRef = useRef(onProviderUpdated);
  const onProviderCreatedRef = useRef(onProviderCreated);
  const onProviderDeletedRef = useRef(onProviderDeleted);
  const onProvidersUpdatedRef = useRef(onProvidersUpdated);
  const onOperationSucceededRef = useRef(onOperationSucceeded);
  onProviderUpdatedRef.current = onProviderUpdated;
  onProviderCreatedRef.current = onProviderCreated;
  onProviderDeletedRef.current = onProviderDeleted;
  onProvidersUpdatedRef.current = onProvidersUpdated;
  onOperationSucceededRef.current = onOperationSucceeded;

  const mark = (providerId: string, status: ProviderOperationStatus) => {
    setStatuses((current) => ({ ...current, [providerId]: status }));
  };

  const run = (provider: ProviderProfile, status: ProviderOperationStatus, operation: () => Promise<void>) => {
    if (gateRef.current.isActive(provider.id)) return;
    mark(provider.id, status);
    void gateRef.current.run(provider.id, operation).catch((error) => {
      mark(provider.id, { type: 'error', message: operationError(error) });
    });
  };

  const saveProvider = (provider: ProviderProfile) => {
    run(provider, { type: 'saving', message: '正在保存 AI 服务配置...' }, async () => {
      await saveProviderProfile(provider);
      mark(provider.id, { type: 'ok', message: 'AI 服务配置已保存到本机服务。' });
      onOperationSucceededRef.current?.();
    });
  };

  const createProvider = (provider: ProviderProfile) => {
    run(provider, { type: 'saving', message: '正在创建 AI 服务...' }, async () => {
      const saved = await saveProviderProfile(provider);
      onProviderCreatedRef.current?.(saved);
      mark(provider.id, { type: 'ok', message: 'AI 服务已创建，可作为默认服务或阶段例外。' });
      onOperationSucceededRef.current?.();
    });
  };

  const saveSecret = (provider: ProviderProfile) => {
    const apiKey = secretInputs[provider.id]?.trim() ?? '';
    if (!apiKey) {
      mark(provider.id, { type: 'error', message: '请先填写 API Key。' });
      return;
    }
    run(provider, { type: 'saving', message: '正在串行保存配置与密钥...' }, async () => {
      await saveProviderProfile(provider);
      await saveProviderSecret(provider.id, apiKey);
      setSecretInputs((current) => ({ ...current, [provider.id]: '' }));
      onProviderUpdatedRef.current({ ...provider, has_saved_secret: true });
      mark(provider.id, { type: 'ok', message: '密钥已保存到本机服务，浏览器不保存明文。' });
      onOperationSucceededRef.current?.();
    });
  };

  const saveAndTestProvider = (provider: ProviderProfile) => {
    const apiKey = secretInputs[provider.id]?.trim() ?? '';
    run(provider, { type: 'saving', message: '正在保存配置并检查连接...' }, async () => {
      const saved = await saveProviderProfile(provider);
      let nextProvider = saved;
      if (apiKey) {
        await saveProviderSecret(provider.id, apiKey);
        nextProvider = { ...saved, has_saved_secret: true };
        setSecretInputs((current) => ({ ...current, [provider.id]: '' }));
      }
      onProviderUpdatedRef.current(nextProvider);
      const result = await testProviderConnection(nextProvider, apiKey);
      mark(provider.id, {
        type: result.ok ? 'ok' : 'error',
        message: result.response_preview ? `${result.message}：${result.response_preview}` : result.message,
        code: result.error_code || undefined,
      });
      onOperationSucceededRef.current?.();
    });
  };

  const deleteProvider = (provider: ProviderProfile) => {
    run(provider, { type: 'deleting', message: '正在删除该 AI 服务的配置和本机密钥...' }, async () => {
      await deleteProviderProfile(provider.id);
      setSecretInputs((current) => {
        const next = { ...current };
        delete next[provider.id];
        return next;
      });
      setStatuses((current) => {
        const next = { ...current };
        delete next[provider.id];
        return next;
      });
      onProviderDeletedRef.current?.(provider.id);
      onOperationSucceededRef.current?.();
    });
  };

  const testProvider = (provider: ProviderProfile) => {
    run(provider, { type: 'testing', message: '正在保存当前配置并进行轻量连通测试...' }, async () => {
      await saveProviderProfile(provider);
      const result = await testProviderConnection(provider, secretInputs[provider.id] ?? '');
      mark(provider.id, {
        type: result.ok ? 'ok' : 'error',
        message: result.response_preview ? `${result.message}：${result.response_preview}` : result.message,
        code: result.error_code || undefined,
      });
      onOperationSucceededRef.current?.();
    });
  };

  const discoverModels = (provider: ProviderProfile) => {
    run(provider, { type: 'discovering', message: '正在读取模型目录，不会生成内容...' }, async () => {
      await saveProviderProfile(provider);
      const result = await discoverProviderModels(provider.id, secretInputs[provider.id] ?? '');
      if (!result.ok) {
        mark(provider.id, { type: 'error', message: result.message, code: result.error_code || undefined });
        return;
      }
      onProviderUpdatedRef.current({
        ...provider,
        model_options: Array.from(new Set([provider.default_model, ...(provider.model_options ?? []), ...result.models].filter(Boolean))),
        model_supported_parameters: result.model_supported_parameters,
      });
      mark(provider.id, { type: 'ok', message: result.message });
      onOperationSucceededRef.current?.();
    });
  };

  const setGlobalDefault = (provider: ProviderProfile) => {
    run(provider, { type: 'saving', message: '正在保存全局默认接口...' }, async () => {
      const updated = await setDefaultProviderProfile(provider.id, provider.kind);
      onProvidersUpdatedRef.current?.(updated);
      mark(provider.id, { type: 'ok', message: '全局默认接口已保存。' });
      onOperationSucceededRef.current?.();
    });
  };

  return {
    clearSecretInputs: () => setSecretInputs({}),
    createProvider,
    deleteProvider,
    discoverModels,
    providerBusy: (providerId: string) => gateRef.current.isActive(providerId),
    saveProvider,
    saveAndTestProvider,
    saveSecret,
    secretInputs,
    setGlobalDefault,
    setSecretInput: (providerId: string, value: string) => setSecretInputs((current) => ({ ...current, [providerId]: value })),
    statuses,
    testProvider,
  };
}

export type ProviderOperations = ReturnType<typeof useProviderOperations>;

function operationError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败，请稍后重试。';
}

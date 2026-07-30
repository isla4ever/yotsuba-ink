import { useEffect, useState } from 'react';
import type { ProviderProfile, ProviderTemplate } from '../contracts';
import { listProviderProfiles, listProviderTemplates } from '../services/providerApi';

type SecretAvailability = Pick<ProviderProfile, 'has_env_secret' | 'has_saved_secret'>;

export type ProviderAvailabilityState = {
  byProvider: Record<string, SecretAvailability>;
  templates: ProviderTemplate[];
  status: 'idle' | 'loading' | 'ready' | 'failed';
};

const initialState: ProviderAvailabilityState = { byProvider: {}, templates: [], status: 'idle' };

export function useProviderAvailability(open: boolean) {
  const [state, setState] = useState<ProviderAvailabilityState>(initialState);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setState((current) => ({ ...current, status: 'loading' }));
    void Promise.all([listProviderProfiles(), listProviderTemplates()])
      .then(([profiles, templates]) => {
        if (!active) return;
        setState({
          byProvider: Object.fromEntries(profiles.map((provider) => [provider.id, {
            has_env_secret: provider.has_env_secret,
            has_saved_secret: provider.has_saved_secret,
          }])),
          templates,
          status: 'ready',
        });
      })
      .catch(() => {
        if (active) setState((current) => ({ ...current, status: 'failed' }));
      });
    return () => {
      active = false;
    };
  }, [open]);

  return state;
}

export function providerSecretStatus(
  provider: ProviderProfile,
  availability: ProviderAvailabilityState,
) {
  const current = availability.byProvider[provider.id];
  if (provider.has_saved_secret || current?.has_saved_secret) return '已保存本地密钥';
  if (provider.has_env_secret || current?.has_env_secret) return '已检测环境密钥';
  if (availability.status === 'loading') return '正在核验密钥状态';
  if (availability.status === 'failed') return '密钥状态未确认';
  return '未保存本地密钥';
}

import { describe, expect, it } from 'vitest';
import type { ProviderTemplate } from '../contracts';
import { providerTemplateOptionItems } from './providerOptionItems';

function template(id: string, integration_tier: ProviderTemplate['integration_tier']): ProviderTemplate {
  return {
    id, label: id, kind: 'openai-compatible', base_url: '', default_model: id, model_options: [], api_key_env: '',
    docs_url: '', integration_tier, description: id, supports_response_format: true, image_size_separator: 'x',
    image_size_field: 'size', image_count_field: 'n', image_response_field: 'data', image_endpoint_path: '',
    models_endpoint_path: '', image_static_parameters: {}, supports_image_quality: false, max_retries: 1,
  };
}

describe('provider option presentation', () => {
  it('orders template groups by integration path without changing order inside a group', () => {
    const options = providerTemplateOptionItems([
      template('custom-a', 'custom'),
      template('gateway-a', 'gateway'),
      template('official-a', 'official'),
      template('official-b', 'official'),
      template('compatibility-a', 'compatibility'),
    ]);

    expect(options.map((item) => item.value)).toEqual([
      'official-a', 'official-b', 'compatibility-a', 'gateway-a', 'custom-a',
    ]);
  });
});

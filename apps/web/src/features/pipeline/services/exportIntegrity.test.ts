import { describe, expect, it } from 'vitest';
import { verifyExportBlob } from './exportIntegrity';

describe('export download integrity', () => {
  it('accepts a blob only when its bytes match the receipt digest', async () => {
    const blob = new Blob(['immutable-export']);
    const sha256 = 'e4b23d2b7598f75c2adcdc84a0cf9e182c982e2d593b8286d9afb2b1cce97a24';

    await expect(verifyExportBlob(blob, {
      expectedSha256: sha256,
      expectedSizeBytes: blob.size,
      responseSha256: sha256,
    })).resolves.toBe(sha256);
  });

  it('rejects response headers that disagree with the receipt', async () => {
    const blob = new Blob(['immutable-export']);
    await expect(verifyExportBlob(blob, {
      expectedSha256: 'a'.repeat(64),
      responseSha256: 'b'.repeat(64),
    })).rejects.toThrow('响应摘要与 Receipt 不一致');
  });

  it('rejects tampered bytes and missing digests before download', async () => {
    const blob = new Blob(['tampered']);
    await expect(verifyExportBlob(blob, { expectedSha256: 'a'.repeat(64) })).rejects.toThrow('SHA-256 校验失败');
    await expect(verifyExportBlob(blob, {})).rejects.toThrow('缺少 SHA-256');
  });

  it('requires a valid response digest when downloading a stored receipt', async () => {
    const blob = new Blob(['immutable-export']);
    const sha256 = 'e4b23d2b7598f75c2adcdc84a0cf9e182c982e2d593b8286d9afb2b1cce97a24';

    await expect(verifyExportBlob(blob, {
      expectedSha256: sha256,
      requireResponseSha256: true,
    })).rejects.toThrow('响应缺少 SHA-256');
    await expect(verifyExportBlob(blob, {
      expectedSha256: sha256,
      responseSha256: 'not-a-digest',
    })).rejects.toThrow('响应的 SHA-256 无效');
  });
});

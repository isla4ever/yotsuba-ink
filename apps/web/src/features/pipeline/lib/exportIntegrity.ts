type ExportIntegrityExpectation = {
  expectedSha256?: string
  expectedSizeBytes?: number
  requireResponseSha256?: boolean
  responseSha256?: string
}

export async function verifyExportBlob(
  blob: Blob,
  expectation: ExportIntegrityExpectation,
): Promise<string> {
  const expectedValue = String(expectation.expectedSha256 || "").trim()
  const responseValue = String(expectation.responseSha256 || "").trim()
  const expected = normalizeDigest(expectedValue)
  const response = normalizeDigest(responseValue)
  if (expectedValue && !expected)
    throw new Error("交付 Receipt 的 SHA-256 无效，已阻止下载。")
  if (responseValue && !response)
    throw new Error("交付响应的 SHA-256 无效，已阻止下载。")
  if (expectation.requireResponseSha256 && !response)
    throw new Error("交付响应缺少 SHA-256，已阻止下载。")
  if (
    expectation.expectedSizeBytes != null &&
    blob.size !== expectation.expectedSizeBytes
  ) {
    throw new Error("交付文件大小与 Receipt 不一致，已阻止下载。")
  }
  if (expected && response && expected !== response)
    throw new Error("交付响应摘要与 Receipt 不一致，已阻止下载。")
  const target = expected || response
  if (!target) throw new Error("交付响应缺少 SHA-256，已阻止下载。")
  if (!globalThis.crypto?.subtle)
    throw new Error("当前浏览器不支持交付文件完整性校验。")
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    await blob.arrayBuffer(),
  )
  const actual = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("")
  if (actual !== target)
    throw new Error("交付文件 SHA-256 校验失败，已阻止下载。")
  return actual
}

function normalizeDigest(value?: string) {
  const digest = String(value || "")
    .trim()
    .toLowerCase()
  return /^[a-f0-9]{64}$/.test(digest) ? digest : ""
}

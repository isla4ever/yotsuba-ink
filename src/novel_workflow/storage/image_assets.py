from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass


class ImageAssetValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ImageAssetInfo:
    mime_type: str
    extension: str
    width: int
    height: int


def inspect_image_asset(content: bytes, declared_mime_type: str = "") -> ImageAssetInfo:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        info = _inspect_png(content)
    elif content.startswith(b"\xff\xd8"):
        info = _inspect_jpeg(content)
    elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        info = _inspect_webp(content)
    else:
        raise ImageAssetValidationError("图片内容不是受支持的 PNG、JPEG 或 WebP")
    declared = declared_mime_type.strip().lower()
    if declared == "image/jpg":
        declared = "image/jpeg"
    if declared and declared != info.mime_type:
        raise ImageAssetValidationError("图片声明 MIME 与实际内容不一致")
    if info.width < 256 or info.height < 256:
        raise ImageAssetValidationError("图片分辨率低于 256x256，不能作为封面资产")
    if info.width > 8192 or info.height > 8192:
        raise ImageAssetValidationError("图片分辨率超过 8192x8192 安全上限")
    if info.width * info.height > 40_000_000:
        raise ImageAssetValidationError("图片像素总量超过安全上限")
    return info


def _inspect_png(content: bytes) -> ImageAssetInfo:
    offset = 8
    width = height = 0
    compressed = bytearray()
    saw_end = False
    while offset + 12 <= len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        kind = content[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(content):
            raise ImageAssetValidationError("PNG 数据块长度无效")
        payload = content[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", content[offset + 8 + length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            raise ImageAssetValidationError("PNG 数据块校验失败")
        if kind == b"IHDR":
            if length != 13 or width or height:
                raise ImageAssetValidationError("PNG IHDR 无效")
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            saw_end = True
            if end != len(content):
                raise ImageAssetValidationError("PNG 尾部包含非图片数据")
            break
        offset = end
    if not width or not height or not compressed or not saw_end:
        raise ImageAssetValidationError("PNG 缺少必要数据块")
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(bytes(compressed), width * height * 8 + height + 1)
        if not decoder.eof or decoder.unconsumed_tail or len(decoded) > width * height * 8 + height:
            raise ImageAssetValidationError("PNG 解压后数据量异常")
    except zlib.error as exc:
        raise ImageAssetValidationError("PNG 像素数据损坏") from exc
    return ImageAssetInfo("image/png", "png", width, height)


def _inspect_jpeg(content: bytes) -> ImageAssetInfo:
    if len(content) < 4 or not content.endswith(b"\xff\xd9"):
        raise ImageAssetValidationError("JPEG 缺少完整结束标记")
    offset = 2
    while offset + 4 <= len(content):
        if content[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        marker = content[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(content):
            break
        length = struct.unpack(">H", content[offset : offset + 2])[0]
        if length < 2 or offset + length > len(content):
            raise ImageAssetValidationError("JPEG 数据段长度无效")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if length < 7:
                raise ImageAssetValidationError("JPEG 尺寸数据无效")
            height, width = struct.unpack(">HH", content[offset + 3 : offset + 7])
            return ImageAssetInfo("image/jpeg", "jpg", width, height)
        offset += length
    raise ImageAssetValidationError("JPEG 缺少可识别的尺寸数据")


def _inspect_webp(content: bytes) -> ImageAssetInfo:
    if len(content) < 30 or struct.unpack("<I", content[4:8])[0] + 8 != len(content):
        raise ImageAssetValidationError("WebP RIFF 长度无效")
    kind = content[12:16]
    payload_size = struct.unpack("<I", content[16:20])[0]
    payload = content[20 : 20 + payload_size]
    if len(payload) != payload_size:
        raise ImageAssetValidationError("WebP 图像数据不完整")
    if kind == b"VP8X" and len(payload) >= 10:
        width = 1 + int.from_bytes(payload[4:7], "little")
        height = 1 + int.from_bytes(payload[7:10], "little")
    elif kind == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
        bits = int.from_bytes(payload[1:5], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
    elif kind == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
        width = struct.unpack("<H", payload[6:8])[0] & 0x3FFF
        height = struct.unpack("<H", payload[8:10])[0] & 0x3FFF
    else:
        raise ImageAssetValidationError("WebP 编码类型或尺寸数据无效")
    return ImageAssetInfo("image/webp", "webp", width, height)

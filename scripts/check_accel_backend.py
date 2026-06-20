"""
Probe available acceleration backends for local training.

Usage:
    python scripts/check_accel_backend.py
    python scripts/check_accel_backend.py --require-accelerator
"""

import argparse
import json
import platform
import sys

import torch


def safe_call(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def probe_cuda():
    available = bool(torch.cuda.is_available())
    info = {
        "available": available,
        "device_count": int(torch.cuda.device_count()) if available else 0,
        "devices": [],
    }
    if available:
        for i in range(info["device_count"]):
            info["devices"].append(
                {
                    "index": i,
                    "name": safe_call(lambda: torch.cuda.get_device_name(i), "unknown"),
                    "total_memory_gb": round(
                        safe_call(lambda: torch.cuda.get_device_properties(i).total_memory, 0) / 1024**3, 2
                    ),
                }
            )
    return info


def probe_xpu():
    has_xpu_attr = hasattr(torch, "xpu")
    available = bool(safe_call(lambda: has_xpu_attr and torch.xpu.is_available(), False))
    count = int(safe_call(lambda: torch.xpu.device_count(), 0)) if available else 0
    devices = []
    for i in range(count):
        name = safe_call(lambda: torch.xpu.get_device_name(i), "unknown")
        props = safe_call(lambda: torch.xpu.get_device_properties(i), None)
        if props is None:
            total_memory_gb = None
        else:
            total_memory_gb = round(getattr(props, "total_memory", 0) / 1024**3, 2)
        devices.append(
            {
                "index": i,
                "name": name,
                "total_memory_gb": total_memory_gb,
            }
        )
    return {
        "has_attr": has_xpu_attr,
        "available": available,
        "device_count": count,
        "devices": devices,
    }


def probe_ipex():
    try:
        import intel_extension_for_pytorch as ipex  # type: ignore

        return {"installed": True, "version": getattr(ipex, "__version__", "unknown")}
    except Exception as e:
        return {"installed": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-accelerator", action="store_true")
    args = parser.parse_args()

    cuda = probe_cuda()
    xpu = probe_xpu()
    ipex = probe_ipex()

    result = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch_version": getattr(torch, "__version__", "unknown"),
        "cuda": cuda,
        "xpu": xpu,
        "ipex": ipex,
        "recommended_device": "cuda"
        if cuda["available"]
        else ("xpu" if xpu["available"] else "cpu"),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.require_accelerator and not (cuda["available"] or xpu["available"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

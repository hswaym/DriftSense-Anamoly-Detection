"""Hardware interrogation and device requirement enforcement."""

from __future__ import annotations

import platform
import shutil
from typing import Any

import psutil


def get_gpu_info() -> str | None:
    """Detect available GPU accelerator if PyTorch is present."""
    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            device_count = torch.cuda.device_count()
            return f"{device_name} (Count: {device_count})"
    except ImportError:
        pass
    return None


def check_hardware(requested_device: str | None = None) -> dict[str, Any]:
    """Inspect and report hardware capabilities.

    Args:
        requested_device: Optional required device ('cpu', 'gpu', 'cuda').
                          If 'gpu' or 'cuda' is requested but missing, raises RuntimeError.

    Returns:
        dict[str, Any]: Diagnostic hardware summary dictionary.
    """
    gpu = get_gpu_info()
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    disk_usage = shutil.disk_usage(".")
    disk_free_gb = round(disk_usage.free / (1024**3), 2)

    hw = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "cpu": platform.processor() or "Unknown CPU",
        "ram_gb": ram_gb,
        "disk_free_gb": disk_free_gb,
        "gpu": gpu,
    }

    if requested_device:
        req = requested_device.lower().strip()
        if req in ("gpu", "cuda") and not gpu:
            raise RuntimeError(
                f"Requested execution device '{requested_device}' is absent. "
                "G4 rule forbids silent fallback to CPU."
            )

    return hw

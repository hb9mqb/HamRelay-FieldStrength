"""Prepare Py1812 integral maps at runtime without redistributing ITU data."""

from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

TARGET = Path("/opt/py1812-runtime/Py1812")
MANUAL = Path("/itu")
FILENAMES = ("DN50.TXT", "N050.TXT")
OFFICIAL_URL = os.environ.get(
    "ITU_P1812_ZIP_URL",
    "https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.1812-8-202509-I!!ZIP-E.zip",
)


def _manual_files() -> dict[str, bytes] | None:
    files = {name: (MANUAL / name).read_bytes() for name in FILENAMES if (MANUAL / name).is_file()}
    return files if len(files) == len(FILENAMES) else None


def _official_files() -> dict[str, bytes]:
    if os.environ.get("ITU_AUTO_DOWNLOAD", "").lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            "ITU maps missing: mount DN50.TXT and N050.TXT at /itu or set ITU_AUTO_DOWNLOAD=1"
        )
    request = urllib.request.Request(
        OFFICIAL_URL, headers={"User-Agent": "HamRelay-FieldStrength/0.1"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    result: dict[str, bytes] = {}
    for member in archive.namelist():
        basename = Path(member).name.upper()
        if basename in FILENAMES:
            result[basename] = archive.read(member)
    if len(result) != len(FILENAMES):
        raise RuntimeError("official P.1812 archive does not contain DN50.TXT and N050.TXT")
    return result


def main() -> None:
    target = TARGET / "P1812.npz"
    if target.is_file():
        return
    manual_files = _manual_files()
    files = manual_files or _official_files()
    matrices = {
        name.removesuffix(".TXT"): np.loadtxt(io.BytesIO(payload))
        for name, payload in files.items()
    }
    np.savez(target, **matrices)
    provenance = {
        "source": "manual /itu mount" if manual_files else OFFICIAL_URL,
        "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()},
    }
    (TARGET / "P1812-map-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

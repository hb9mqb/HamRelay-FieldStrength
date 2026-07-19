# Windows support

> **Experimental / untested:** the Windows path has not yet been verified on a
> physical Windows system or by a successful public CI run. The implementation
> and CI matrix are prepared, but Windows must not yet be described as supported
> for production calculations.

The intended target is Windows 11 with Python 3.11+. Install from PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

Rasterio wheels provide the required GDAL runtime; do not mix an unrelated
system GDAL DLL directory into `PATH`. The engine uses Windows `spawn` workers
and named shared memory, avoiding a private terrain copy per process. Keep
custom program entry points behind `if __name__ == "__main__"`.

The NumPy rasterizer is authoritative on Windows. MLX/Metal is excluded by
platform markers. Future DirectML, CUDA or SYCL backends should remain optional
and must pass numerical-equivalence tests against NumPy.

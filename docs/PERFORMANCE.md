# Performance and portability

## Apple M5 optimization

The native macOS path is designed for Apple M5 systems:

1. `hw.perflevel0.physicalcpu` selects performance cores, reserving one or two
   for macOS and interactive applications.
2. Large terrain and radio-climate arrays use POSIX shared memory so macOS
   `spawn` workers do not each receive a private raster copy.
3. BLAS/OpenMP thread counts are held at one per worker to prevent nested
   oversubscription.
4. Independent azimuths are chunked across CPU processes; the branch-heavy
   P.1812 routines stay on CPU cores.
5. With the `apple` extra installed, a fused MLX Metal kernel performs the large
   polar-to-Cartesian interpolation. NumPy remains the reference fallback.

Install the optional native backend with:

```bash
python -m pip install -e '.[apple]'
```

Metal is not accessible from a Docker Desktop Linux guest. Run the calculator
natively on macOS when GPU interpolation is desired; the artifact API may still
run in a container.

## Porting opportunities

Contributions for other systems should preserve one reference NumPy path and
verify maximum absolute/relative error before advertising a backend.

| Platform | Suggested work |
|---|---|
| Linux x86-64/ARM64 | NUMA-aware worker placement, `forkserver`, shared memory, SIMD profiling |
| Windows | `spawn` shared-memory lifecycle, Job Object limits, long-path CI |
| NVIDIA | CUDA/CuPy or Numba kernel for polar interpolation and tile coloring |
| AMD | ROCm/HIP backend with the same interpolation contract |
| Intel | oneAPI/SYCL backend; test discrete and integrated GPUs |
| Cross-vendor native | Vulkan compute through a small optional extension |
| Browser | WebGPU numerical-tile compositing and cursor sampling |

P.1812 contains branching and many short path-specific calculations. Moving the
entire method to a GPU may underperform a well-scheduled CPU implementation and
is harder to validate. Begin with raster interpolation, palette application and
large independent batches. Publish hardware, operating-system version, compiler,
wall time, energy, memory peak and numerical error with each benchmark.

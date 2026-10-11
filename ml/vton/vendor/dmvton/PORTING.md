# DM-VTON inference port

Upstream: https://github.com/KiseKloset/DM-VTON/tree/5dcd04ee3f5b1fb392df1184c887c1a7e910c72e

The original source hashes are recorded in `upstream-manifest.json`. The
original LICENSE is retained. The `.txt` sources are unmodified references,
not executable dependencies. The upstream correlation implementation credits
FlowNet2; its attribution is retained in `models/common/correlation.py.txt`.

Local modifications: package-relative imports; explicit `meshgrid(indexing="ij")`;
`interpolate` replaces the deprecated identical `upsample` alias; cost correlation
is implemented with standard PyTorch tensor operators instead of CuPy/CUDA.
The correlation's displacement ordering, zero padding, stride and channel
normalization are checked against an independent scalar reference in tests.

The inference-only adapter in `ml/vton/dmvton.py` follows the vendored official
pipeline and normalization. It uses pinned official checkpoint SHA-256 hashes,
restricted `torch.load(weights_only=True)` with narrowly scoped NumPy scalar
constructors, and strict state dictionaries. It does not invoke the upstream
unsafe pickle loader or initialize substitute weights when loading fails.

Native output is 192x256. This is the released upper-body research model; valid
numerical inference does not establish natural fitting or production quality.

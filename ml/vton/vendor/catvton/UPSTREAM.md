# CatVTON vendored inference

Source: https://github.com/Zheng-Chong/CatVTON/tree/999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e

Only package-relative imports are changed. The application subclasses the official pipeline for verified local loading, FP16, sequential classifier-free guidance and memory management. The original NVIDIA/Creative Commons notices are retained; CatVTON code/checkpoints use CC BY-NC-SA 4.0 and are not cleared for commercial deployment.

The official pipeline accepts a caller-provided binary inpainting mask. The application uses FASHN semantic parsing rather than CatVTON's optional SCHP/DensePose automatic mask generator.

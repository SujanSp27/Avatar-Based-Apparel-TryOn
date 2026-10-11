# Vendored FASHN Human Parser

Official source: https://github.com/fashn-AI/fashn-human-parser

Pinned commit: `f2771f2fb8655349e87e2869bbde7ace0bd06f2c`. The three Python files and LICENSE are unmodified. The upstream license notice and its NVIDIA license link are retained in LICENSE.

The local adapter reuses official preprocessing/prediction but bypasses the upstream constructor to enforce local_files_only=True and safetensors loading. No model or image is uploaded by inference. The model uses 18 labels; neck/left/right limbs are not separate predicted classes.

The application compositor is separate from upstream inference. It replaces all predicted old clothing at full opacity and preserves predicted face, hair, arms, hands, background and unrelated clothing exactly. Only generated clothing adjacent to the old neckline on predicted bare torso may extend the mask. This is intentionally conservative: changes to sleeve length, hem length or the original outer silhouette may be clipped. Semantic masks and unchanged pixels do not establish realistic fitting; final neural outputs require visual review.

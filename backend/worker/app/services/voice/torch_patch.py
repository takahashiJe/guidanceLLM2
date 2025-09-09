# backend/worker/app/services/voice/torch_patch.py

import logging
import sys

logger = logging.getLogger("torch_patch")

# このスクリプトは PYTHONSTARTUP 経由で対話的でないプロセス(サブプロセス)からも読み込まれるため、
# 標準エラー出力(stderr)にログを出すように設定します。
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

try:
    import torch, torch.serialization
    # XTTS周辺
    import TTS.tts.models.xtts as xtts_mod
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsAudioConfig
    # 共有config
    from TTS.config.shared_configs import BaseDatasetConfig
    try:
        from TTS.config.shared_configs import BaseAudioConfig
    except Exception:
        BaseAudioConfig = None

    allow = set()
    # XTTSモジュール内の Args／Config／AudioConfig を総なめ
    for name in dir(xtts_mod):
        obj = getattr(xtts_mod, name, None)
        if isinstance(obj, type) and (
            name.endswith("Args") or name.endswith("Config") or name.endswith("AudioConfig")
        ):
            allow.add(obj)

    # 明示的に重要どころを追加（保険）
    allow.update({
        XttsConfig,
        XttsAudioConfig,
        getattr(xtts_mod, "XttsArgs", None),
    })

    # 共有config
    allow.add(BaseDatasetConfig)
    if BaseAudioConfig:
        allow.add(BaseAudioConfig)

    torch.serialization.add_safe_globals([c for c in allow if c is not None])

except ImportError:
    logger.warning(
        "Failed to import TTS/Torch modules during PYTHONSTARTUP patch. "
        "Subprocess (TTS CLI) may fail with UnpicklingError."
    )
except Exception as e:
    logger.error(f"Error applying Torch subprocess patch via PYTHONSTARTUP: {e}")
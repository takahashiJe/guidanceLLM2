# backend/worker/app/services/voice/torch_patch.py

import logging, sys
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger("torch_patch")

try:
    import torch, torch.serialization
    import inspect

    # XTTS周辺のモジュールとクラス
    import TTS.tts.models.xtts as xtts_mod
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsAudioConfig

    # 共有config
    try:
        from TTS.config.shared_configs import BaseDatasetConfig, BaseAudioConfig
    except Exception:
        from TTS.config.shared_configs import BaseDatasetConfig
        BaseAudioConfig = None

    allow = set()

    # XTTSモジュール内の Args／Config／AudioConfig を総なめ
    for name in dir(xtts_mod):
        obj = getattr(xtts_mod, name, None)
        if inspect.isclass(obj) and (
            name.endswith("Args") or name.endswith("Config") or name.endswith("AudioConfig")
        ):
            allow.add(obj)

    # 明示的に主要クラスを追加（保険）
    allow.update({
        XttsConfig,
        XttsAudioConfig,
        getattr(xtts_mod, "XttsArgs", None),
        BaseDatasetConfig,
    })
    if BaseAudioConfig is not None:
        allow.add(BaseAudioConfig)

    torch.serialization.add_safe_globals([c for c in allow if c is not None])
    logger.debug("Torch safe_globals patch applied successfully for subprocess.")
except ImportError:
    logger.warning(
        "Failed to import TTS/Torch modules during PYTHONSTARTUP patch. "
        "Subprocess (TTS CLI) may fail with UnpicklingError."
    )
except Exception as e:
    logger.error(f"Error applying Torch subprocess patch via PYTHONSTARTUP: {e}")

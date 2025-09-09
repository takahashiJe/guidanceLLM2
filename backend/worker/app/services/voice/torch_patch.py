# /opt/torch_patch.py
import sys, logging, inspect
print("[torch_patch] starting…", file=sys.stderr, flush=True)
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
log = logging.getLogger("torch_patch")

try:
    import torch, torch.serialization
    import TTS.tts.models.xtts as xtts_mod
    from TTS.tts.configs.xtts_config import XttsConfig
    from TTS.tts.models.xtts import XttsAudioConfig
    try:
        # ある環境では BaseAudioConfig が無いので try/except にする
        from TTS.config.shared_configs import BaseDatasetConfig, BaseAudioConfig
    except Exception:
        from TTS.config.shared_configs import BaseDatasetConfig
        BaseAudioConfig = None

    allow = set()
    # XTTS内の *Args / *Config / *AudioConfig を総なめ
    for name in dir(xtts_mod):
        obj = getattr(xtts_mod, name, None)
        if inspect.isclass(obj) and (
            name.endswith("Args") or name.endswith("Config") or name.endswith("AudioConfig")
        ):
            allow.add(obj)

    # 明示的に押さえておく主要クラス（保険）
    allow.update({
        XttsConfig,
        XttsAudioConfig,
        getattr(xtts_mod, "XttsArgs", None),
        BaseDatasetConfig,
    })
    if BaseAudioConfig is not None:
        allow.add(BaseAudioConfig)

    # None を取り除いて登録
    torch.serialization.add_safe_globals([c for c in allow if c is not None])
    log.debug("[torch_patch] applied: %d classes", len(allow))
except Exception as e:
    log.error("[torch_patch] failed: %s", e)

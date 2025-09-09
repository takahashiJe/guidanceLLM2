# backend/worker/app/services/voice/torch_patch.py

import logging
import sys

logger = logging.getLogger("torch_patch")

# このスクリプトは PYTHONSTARTUP 経由で対話的でないプロセス(サブプロセス)からも読み込まれるため、
# 標準エラー出力(stderr)にログを出すように設定します。
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

try:
    import torch.serialization
    from TTS.tts.configs.xtts_config import XttsConfig
    import TTS.tts.configs.xtts_config

    # PyTorch 2.6+ セキュリティパッチ (UnpicklingError対策)
    # torch.serialization.add_safe_globals([XttsConfig])
    torch.serialization.add_safe_globals([XttsConfig, TTS.tts.configs.xtts_config.XttsConfig])
    logger.debug("Torch safe_globals patch applied successfully for subprocess environment.")

except ImportError:
    logger.warning(
        "Failed to import TTS/Torch modules during PYTHONSTARTUP patch. "
        "Subprocess (TTS CLI) may fail with UnpicklingError."
    )
except Exception as e:
    logger.error(f"Error applying Torch subprocess patch via PYTHONSTARTUP: {e}")
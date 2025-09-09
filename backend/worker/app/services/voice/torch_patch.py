# この内容で torch_patch.py という名前のファイルを tts.py と同じディレクトリに作成します

import logging
import sys

logger = logging.getLogger("torch_patch")

# このスクリプトは PYTHONSTARTUP 経由で対話的でないプロセス(サブプロセス)からも読み込まれるため、
# 標準エラー出力(stderr)にログを出すように設定します。
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

try:
    import torch.serialization
    from TTS.tts.configs.xtts_config import XttsConfig

    # PyTorch 2.6+ セキュリティパッチ (UnpicklingError対策)
    torch.serialization.add_safe_globals([XttsConfig])
    logger.debug("Torch safe_globals patch applied successfully for subprocess environment.")

except ImportError:
    logger.warning(
        "Failed to import TTS/Torch modules during PYTHONSTARTUP patch. "
        "Subprocess (TTS CLI) may fail with UnpicklingError."
    )
except Exception as e:
    logger.error(f"Error applying Torch subprocess patch via PYTHONSTARTUP: {e}")
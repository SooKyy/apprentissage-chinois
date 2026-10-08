import hashlib
import os
from pathlib import Path

import edge_tts

from app.config import get_settings

MAX_CHARS = 200


class TTSError(Exception):
    pass


def cache_path(text: str) -> Path:
    settings = get_settings()
    digest = hashlib.sha256(f"{settings.tts_voice}|{text}".encode("utf-8")).hexdigest()[:32]
    return Path(settings.tts_cache_dir) / f"{digest}.mp3"


async def synthesize(text: str) -> Path:
    """Rend le MP3 du texte, généré une seule fois puis servi depuis le cache disque."""
    path = cache_path(text)
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(f".{os.getpid()}.part")
    try:
        await edge_tts.Communicate(text, get_settings().tts_voice).save(str(partial))
        if partial.stat().st_size == 0:
            raise TTSError("audio vide")
        os.replace(partial, path)
    except TTSError:
        raise
    except Exception as exc:  # edge-tts lève des exceptions variées (réseau, service)
        raise TTSError(f"synthèse vocale indisponible : {type(exc).__name__}") from exc
    finally:
        partial.unlink(missing_ok=True)
    return path

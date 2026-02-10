"""
EcoCoin — Chiqindi aniqlash ovozi.
audio/eat/ papkasidan random .ogg/.wav fayl o'ynaydi.
PyQt6 QMediaPlayer ishlatadi (tashqi dastur ochmaydi).
"""

import random
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).parent.parent / "audio"

# PyQt6 media player — bir marta yaratiladi
_player = None
_audio_output = None


def _ensure_player():
    """QMediaPlayer va QAudioOutput yaratish (faqat birinchi chaqiruvda)."""
    global _player, _audio_output
    if _player is not None:
        return

    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return

    _audio_output = QAudioOutput()
    _audio_output.setVolume(1.0)
    _player = QMediaPlayer()
    _player.setAudioOutput(_audio_output)


def play_detection_sound():
    """audio/eat/ dan random faylni o'ynash."""
    try:
        _ensure_player()
        if _player is None:
            return

        folder = AUDIO_DIR / "eat"
        if not folder.exists():
            return

        files = [
            f for f in folder.iterdir()
            if f.suffix.lower() in ('.ogg', '.wav', '.mp3', '.m4a', '.wma')
        ]
        if not files:
            return

        filepath = random.choice(files)

        from PyQt6.QtCore import QUrl
        _player.setSource(QUrl.fromLocalFile(str(filepath)))
        _player.play()
        logger.debug(f"Audio: {filepath.name}")

    except Exception as e:
        logger.debug(f"Audio xato: {e}")

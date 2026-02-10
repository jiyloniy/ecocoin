"""
EcoCoin Kiosk — UI bilan ishga tushirish.

Foydalanish:
    python app.py              # Oddiy oyna
    python app.py --fullscreen # To'liq ekran
    python app.py --camera 1   # Boshqa kamera
"""

import sys
import argparse
import logging
import os

# Torch DLL xatosini oldini olish (PyQt6 bilan conflict)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
try:
    import torch  # noqa: F401  — torch ni PyQt6 dan oldin yuklash
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.kiosk import KioskWindow


def main():
    parser = argparse.ArgumentParser(description="EcoCoin Kiosk")
    parser.add_argument("--camera", "-c", type=int, default=0, help="Kamera indeksi")
    parser.add_argument("--fullscreen", "-f", action="store_true", help="To'liq ekran rejimi")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Global dark theme
    app.setStyleSheet("""
        * {
            font-family: 'Segoe UI', Arial, sans-serif;
        }
    """)

    window = KioskWindow()

    if args.fullscreen:
        window.showFullScreen()
    else:
        window.resize(900, 700)
        window.show()

    window.start(camera_index=args.camera)

    print("\n🌿 EcoCoin Kiosk ishga tushdi!")
    print("   F / F11 — To'liq ekran")
    print("   ESC / Q — Chiqish\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

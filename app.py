

import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("ecocoin")

# Windows da PyTorch DLL larini PyQt6 dan OLDIN yuklash kerak
# (aks holda c10.dll "WinError 1114" xatosi chiqadi)
try:
    import torch  # noqa: F401
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description="EcoCoin Kiosk")
    parser.add_argument("--camera", type=int, default=0, help="Kamera indeksi (default: 0)")
    parser.add_argument("--fullscreen", action="store_true", help="To'liq ekran rejimi")
    args = parser.parse_args()

    # PyQt6 import
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
    except ImportError:
        logger.error("PyQt6 o'rnatilmagan! pip install PyQt6")
        sys.exit(1)

    from ui.kiosk import KioskWindow

    app = QApplication(sys.argv)
    app.setApplicationName("EcoCoin")

    window = KioskWindow()

    if args.fullscreen:
        window.showFullScreen()
    else:
        window.showMaximized()

    window.start(camera_index=args.camera)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""
EcoCoin - Chiqindilarni saralash tizimi.
Asosiy ishga tushirish fayli.

Foydalanish:
    # Kamera rejimi (real-vaqt):
    python main.py

    # Bitta rasmni tahlil qilish:
    python main.py --image rasm.jpg

    # Boshqa kamera (masalan index 1):
    python main.py --camera 1
"""

import sys
import argparse
import logging

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ecocoin")


def on_waste_detected(detections):
    """Chiqindi aniqlanganda chaqiriladigan callback."""
    for det in detections:
        if det.waste_category != "unknown":
            logger.debug(
                f"Aniqlandi: {det.name_uz} "
                f"(ishonch: {det.confidence:.0%}, "
                f"+{det.ecocoin_reward} EcoCoin)"
            )


def run_camera_mode(camera_index: int = 0):
    """Kamera rejimini ishga tushirish."""
    from ai.camera import CameraDetector

    print("\n🌿 EcoCoin - Chiqindilarni Saralash Tizimi")
    print("   AI model yuklanmoqda...\n")

    detector = CameraDetector(
        camera_index=camera_index,
        on_detection=on_waste_detected,
    )
    detector.run()


def run_image_mode(image_path: str):
    """Bitta rasmni tahlil qilish rejimi."""
    from ai.camera import CameraDetector

    print("\n🌿 EcoCoin - Rasm Tahlili")
    print("   AI model yuklanmoqda...\n")

    detector = CameraDetector()
    detections = detector.detect_from_image(image_path)

    if detections:
        summary = detector.classifier.get_summary(detections)
        print(f"\n   Natija: {summary['total_ecocoins']} EcoCoin topildi!")
    return detections


def main():
    parser = argparse.ArgumentParser(
        description="EcoCoin - Chiqindilarni saralash AI tizimi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Misollar:
  python main.py                  # Kamerani ishga tushirish
  python main.py --image test.jpg # Rasmni tahlil qilish
  python main.py --camera 1       # Boshqa kamera
        """,
    )
    parser.add_argument(
        "--image", "-i",
        type=str,
        help="Rasm fayli yo'li (kamera o'rniga rasmdan aniqlash)",
    )
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="Kamera indeksi (default: 0)",
    )

    args = parser.parse_args()

    if args.image:
        run_image_mode(args.image)
    else:
        run_camera_mode(args.camera)


if __name__ == "__main__":
    main()

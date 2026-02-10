"""
EcoCoin AI tizimini test qilish.
"""

import os
import sys
import cv2
import numpy as np

# Loyiha root papkasini path ga qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.classifier import WasteClassifier
from ai.config import WASTE_CATEGORIES


def test_model_loading():
    """Model yuklanishini tekshirish."""
    print("1. Model yuklanishini tekshirish...")
    try:
        classifier = WasteClassifier()
        assert classifier.is_loaded, "Model yuklanmadi!"
        print("   ✅ Model muvaffaqiyatli yuklandi")
        return classifier
    except Exception as e:
        print(f"   ❌ Xato: {e}")
        return None


def test_detection_with_dummy_image(classifier: WasteClassifier):
    """Bo'sh rasm bilan aniqlashni tekshirish."""
    print("\n2. Bo'sh rasm bilan test...")
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = classifier.detect(dummy_frame)
    print(f"   ✅ Aniqlash ishladi. Topilgan: {len(detections)} ta obyekt")
    return True


def test_detection_with_real_image(classifier: WasteClassifier, image_path: str):
    """Haqiqiy rasm bilan aniqlashni tekshirish."""
    print(f"\n3. Haqiqiy rasm bilan test: {image_path}")

    if not os.path.exists(image_path):
        print(f"   ⚠️  Rasm topilmadi: {image_path}")
        return False

    detections = classifier.detect_single_image(image_path)
    summary = classifier.get_summary(detections)

    print(f"   ✅ Topilgan: {summary['total_items']} ta obyekt")
    print(f"   💰 EcoCoin: {summary['total_ecocoins']}")

    for det in detections:
        print(
            f"      - {det.name_uz}: {det.confidence:.0%} "
            f"(+{det.ecocoin_reward} EcoCoin)"
        )

    return True


def test_categories():
    """Kategoriyalar konfiguratsiyasini tekshirish."""
    print("\n4. Kategoriyalar tekshiruvi...")
    for key, cat in WASTE_CATEGORIES.items():
        assert "name_uz" in cat, f"{key}: name_uz yo'q"
        assert "ecocoin_reward" in cat, f"{key}: ecocoin_reward yo'q"
        print(f"   {cat['icon']} {cat['name_uz']} = {cat['ecocoin_reward']} EcoCoin")
    print("   ✅ Barcha kategoriyalar to'g'ri")
    return True


def main():
    print("=" * 50)
    print("  EcoCoin AI - Test")
    print("=" * 50)

    # 1. Model test
    classifier = test_model_loading()
    if classifier is None:
        print("\n❌ Model yuklanmadi. Testlar to'xtatildi.")
        sys.exit(1)

    # 2. Dummy image test
    test_detection_with_dummy_image(classifier)

    # 3. Real image test (agar rasm berilgan bo'lsa)
    if len(sys.argv) > 1:
        test_detection_with_real_image(classifier, sys.argv[1])

    # 4. Kategoriyalar test
    test_categories()

    print("\n" + "=" * 50)
    print("  ✅ Barcha testlar muvaffaqiyatli o'tdi!")
    print("=" * 50)


if __name__ == "__main__":
    main()

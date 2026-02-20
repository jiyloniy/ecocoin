"""
EcoCoin — YOLOv8 modelni ONNX formatga eksport qilish.

BU SKRIPTNI FAQAT PC DA ISHLATING (torch/ultralytics kerak).
Keyin yolov8n.onnx faylni Raspberry Pi ga ko'chiring.

Foydalanish / Usage:
    python export_onnx.py
    python export_onnx.py --model yolov8n.pt --output yolov8n.onnx

Natija:
    yolov8n.onnx fayl yaratiladi — RPi da onnxruntime bilan ishlatish uchun.
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="YOLOv8 modelni ONNX formatga eksport qilish (faqat PC da)"
    )
    parser.add_argument(
        "--model", type=str, default="yolov8n.pt",
        help="PyTorch model fayl nomi (default: yolov8n.pt)"
    )
    parser.add_argument(
        "--output", type=str, default="yolov8n.onnx",
        help="Chiqish ONNX fayl nomi (default: yolov8n.onnx)"
    )
    parser.add_argument(
        "--imgsz", type=int, default=640,
        help="Rasm o'lchami (default: 640)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"❌ Model fayl topilmadi: {args.model}")
        print("   Avval yolov8n.pt faylni yuklab oling yoki to'g'ri yo'lni ko'rsating.")
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ ultralytics o'rnatilmagan!")
        print("   pip install ultralytics")
        sys.exit(1)

    print(f"📦 Model yuklanmoqda: {args.model}")
    model = YOLO(args.model)

    print(f"🔄 ONNX ga eksport qilinmoqda (imgsz={args.imgsz})...")
    export_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        opset=12,
    )

    # Agar ultralytics boshqa nom bersa, nomini o'zgartiramiz
    if export_path and os.path.exists(export_path) and export_path != args.output:
        if os.path.exists(args.output):
            os.remove(args.output)
        os.rename(export_path, args.output)

    if os.path.exists(args.output):
        size_mb = os.path.getsize(args.output) / (1024 * 1024)
        print(f"\n✅ Tayyor! {args.output} ({size_mb:.1f} MB)")
        print(f"\n📋 Keyingi qadamlar:")
        print(f"   1. '{args.output}' faylni Raspberry Pi ga ko'chiring")
        print(f"   2. RPi da: pip install onnxruntime opencv-python numpy")
        print(f"   3. RPi da: python main.py yoki python app.py")
    else:
        print("❌ Eksport muvaffaqiyatsiz bo'ldi!")
        sys.exit(1)


if __name__ == "__main__":
    main()

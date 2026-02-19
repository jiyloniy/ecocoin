"""
Chiqindilarni saralash tizimi konfiguratsiyasi.
Waste sorting system configuration.
"""

# ─── Chiqindi kategoriyalari / Waste Categories ───
WASTE_CATEGORIES = {
    "bottle": {
        "name_uz": "Plastik shisha",
        "name_en": "Plastic Bottle",
        "material": "plastic",
        "ecocoin_reward": 5,  # har bir chiqindi uchun 5 coin
        "bin_color": "sariq",  # yellow
        "icon": "🧴",
    },
    "cup": {
        "name_uz": "Stakan / Piyola",
        "name_en": "Cup",
        "material": "plastic",
        "ecocoin_reward": 5,
        "bin_color": "sariq",
        "icon": "🥤",
    },
    "glass": {
        "name_uz": "Shisha idish",
        "name_en": "Glass",
        "material": "glass",
        "ecocoin_reward": 5,
        "bin_color": "yashil",  # green
        "icon": "🍶",
    },
    "can": {
        "name_uz": "Metall quti",
        "name_en": "Metal Can",
        "material": "metal",
        "ecocoin_reward": 6,
        "bin_color": "ko'k",  # blue
        "icon": "🥫",
    },
    
    
    
    "unknown": {
        "name_uz": "Noma'lum",
        "name_en": "Unknown",
        "material": "unknown",
        "ecocoin_reward": 0,
        "bin_color": "kulrang",  # gray
        "icon": "❓",
    },

}

# ─── YOLO COCO klasslarini chiqindi kategoriyalariga moslashtirish ───
# Mapping YOLO COCO class names → our waste categories
YOLO_TO_WASTE = {
    "bottle":     "bottle",
    "cup":        "cup",
    "wine glass": "glass",
    "bowl":       "glass",
    "vase":       "glass",
    "book":       "paper",
    "handbag":    "plastic_bag",
    "suitcase":   "cardboard",
    
}

# ─── Model sozlamalari / Model settings ───
MODEL_NAME = "yolov8n.pt"          # YOLOv8-nano (eng yengil va tez)
CONFIDENCE_THRESHOLD = 0.30        # Minimal ishonch darajasi (pastroq = yuqoridan ham taniydi)
IOU_THRESHOLD = 0.45               # Non-max suppression

# ─── Dumaloq shakl aniqlash (bottle cap) sozlamalari ───
CIRCLE_DETECTION = True            # Dumaloq shakl orqali ham aniqlash
CIRCLE_MIN_RADIUS = 20             # Minimal radius (piksel)
CIRCLE_MAX_RADIUS = 150            # Maksimal radius (piksel)

# ─── Kamera sozlamalari / Camera settings ───
CAMERA_INDEX = 0                   # Default kamera
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
FPS = 30

# ─── Raspberry Pi kamera sozlamalari ───
# "auto" = avtomatik aniqlash, "picamera" = RPi CSI kamera, "opencv" = USB webcam
CAMERA_BACKEND = "auto"
# picamera2 uchun qo'shimcha sozlamalar
RPI_CAMERA_ROTATION = 0            # Kamera burchagi: 0, 90, 180, 270
RPI_CAMERA_HFLIP = False           # Gorizontal aks
RPI_CAMERA_VFLIP = False           # Vertikal aks

# ─── UI sozlamalari ───
WINDOW_NAME = "EcoCoin - Chiqindilarni Saralash"
FONT_SCALE = 0.7
FONT_THICKNESS = 2

# Ranglar (BGR format)
COLORS = {
    "sariq":   (0, 255, 255),   # Yellow  - plastik
    "yashil":  (0, 255, 0),     # Green   - shisha
    "ko'k":    (255, 128, 0),   # Blue    - qog'oz/metall
    "kulrang": (128, 128, 128), # Gray    - noma'lum
    "oq":      (255, 255, 255), # White   - matn
    "qora":    (0, 0, 0),       # Black   - fon
}

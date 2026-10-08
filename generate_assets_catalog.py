#!/usr/bin/env python3
"""
SmartRMA Asset Suite Generator:
Generates 100+ distinct hardware inspection images across different components,
angles, perspectives, optical filters, and thermal anomaly modalities.
"""

import os
import json
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

ASSETS_DIR = "/Users/happydeswal/Downloads/files/assets"
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"

try:
    FONT_MD = ImageFont.truetype(FONT_PATH, 16)
    FONT_SM = ImageFont.truetype(FONT_PATH, 12)
    FONT_XS = ImageFont.truetype(FONT_PATH, 10)
    FONT_LG = ImageFont.truetype(FONT_PATH, 20)
except Exception:
    FONT_MD = FONT_SM = FONT_XS = FONT_LG = ImageFont.load_default()

# Base source images
BASE_SOURCES = {
    'core': os.path.join(ASSETS_DIR, 'gpu_reference.jpg'),
    'vrm': os.path.join(ASSETS_DIR, 'base_vrm.jpg'),
    'pcie': os.path.join(ASSETS_DIR, 'base_pcie.jpg'),
    'power': os.path.join(ASSETS_DIR, 'gpu_damaged.jpg'),
    'backplate': os.path.join(ASSETS_DIR, 'base_backplate.jpg'),
    'shroud': os.path.join(ASSETS_DIR, 'gpu_front.jpg')
}

# Load and prepare base images
loaded_bases = {}
for k, path in BASE_SOURCES.items():
    if os.path.exists(path):
        loaded_bases[k] = Image.open(path).convert('RGB')
    else:
        print(f"Warning: Base source {path} not found.")

TARGET_SIZE = (800, 600)

COMPONENTS = [
    {
        'id': 'gpu_silicon_core',
        'name': 'GPU Silicon Core Die (GA102-300-A1)',
        'base': 'core',
        'crop_box': (0.45, 0.28, 0.82, 0.70),
        'scale_mm': 1.0
    },
    {
        'id': 'gddr6x_vram_bank_a',
        'name': 'GDDR6X VRAM Array Bank A (Micron D9WCW)',
        'base': 'core',
        'crop_box': (0.35, 0.12, 0.78, 0.45),
        'scale_mm': 0.8
    },
    {
        'id': 'gddr6x_vram_bank_b',
        'name': 'GDDR6X VRAM Array Bank B (Lower Substrate)',
        'base': 'core',
        'crop_box': (0.62, 0.55, 0.95, 0.88),
        'scale_mm': 0.8
    },
    {
        'id': 'power_12vhpwr_socket',
        'name': '12VHPWR 16-Pin Power Connector Terminal',
        'base': 'power',
        'crop_box': (0.20, 0.15, 0.75, 0.72),
        'scale_mm': 0.5
    },
    {
        'id': 'power_12vhpwr_pins',
        'name': '12VHPWR Header Micro-Pin Array & Shunt',
        'base': 'power',
        'crop_box': (0.32, 0.28, 0.68, 0.62),
        'scale_mm': 0.25
    },
    {
        'id': 'pcie4_gold_fingers',
        'name': 'PCIe 4.0 x16 Gold Contact Edge Fingers',
        'base': 'pcie',
        'crop_box': (0.05, 0.15, 0.95, 0.85),
        'scale_mm': 1.5
    },
    {
        'id': 'pcie_retention_notch',
        'name': 'PCIe Retention Key Notch & Ground Trace',
        'base': 'pcie',
        'crop_box': (0.0, 0.05, 0.50, 0.65),
        'scale_mm': 1.0
    },
    {
        'id': 'vrm_r22_power_chokes',
        'name': 'VRM Multi-Phase R22 Power Choke Array',
        'base': 'vrm',
        'crop_box': (0.30, 0.35, 0.88, 0.72),
        'scale_mm': 1.2
    },
    {
        'id': 'vrm_capacitors_solid',
        'name': 'Solid Electrolytic Capacitors & FETs',
        'base': 'vrm',
        'crop_box': (0.45, 0.32, 0.85, 0.65),
        'scale_mm': 0.6
    },
    {
        'id': 'motherboard_heatsink_vrm',
        'name': 'Strix Aluminum Anodized VRM Heatpipe Heatsink',
        'base': 'vrm',
        'crop_box': (0.02, 0.12, 0.48, 0.60),
        'scale_mm': 3.0
    },
    {
        'id': 'backplate_serial_barcode',
        'name': 'Backplate Serial Barcode 1D/2D Label',
        'base': 'backplate',
        'crop_box': (0.32, 0.35, 0.68, 0.65),
        'scale_mm': 2.0
    },
    {
        'id': 'backplate_tamper_seal',
        'name': 'Security Warranty Tamper Holographic Seal',
        'base': 'backplate',
        'crop_box': (0.58, 0.22, 0.82, 0.48),
        'scale_mm': 0.5
    },
    {
        'id': 'backplate_retention_bracket',
        'name': 'GPU Core Spring Retention X-Bracket & Screws',
        'base': 'backplate',
        'crop_box': (0.0, 0.05, 0.45, 0.60),
        'scale_mm': 2.5
    },
    {
        'id': 'cooling_fan_blades',
        'name': 'Axial-Tech Cooling Fan Blades & Cowling',
        'base': 'shroud',
        'crop_box': (0.32, 0.25, 0.68, 0.75),
        'scale_mm': 5.0
    },
    {
        'id': 'shroud_faceplate_fascia',
        'name': 'Brushed Aluminum Outer Shroud & Logo',
        'base': 'shroud',
        'crop_box': (0.05, 0.05, 0.95, 0.45),
        'scale_mm': 8.0
    }
]

ANGLES = [
    {
        'id': 'ortho_90',
        'name': 'Orthographic 90° Perpendicular Top View',
        'rotate': 0,
        'flip_h': False,
        'gantry_tag': 'GANTRY-Z90'
    },
    {
        'id': 'iso_45_left',
        'name': 'Isometric 45° Oblique Left Quad Light',
        'rotate': -15,
        'flip_h': False,
        'gantry_tag': 'GANTRY-ISO-L'
    },
    {
        'id': 'iso_45_right',
        'name': 'Isometric 45° Oblique Right Quad Light',
        'rotate': 15,
        'flip_h': True,
        'gantry_tag': 'GANTRY-ISO-R'
    },
    {
        'id': 'grazing_15',
        'name': 'Low Grazing Angle 15° Specular Reflection',
        'rotate': 3,
        'flip_h': False,
        'gantry_tag': 'GANTRY-GRAZE15'
    },
    {
        'id': 'micro_10x_zoom',
        'name': 'Microscopic High-Magnification Zoom 10x',
        'rotate': 0,
        'flip_h': False,
        'gantry_tag': 'OPTIC-MAG10X'
    },
    {
        'id': 'inverted_profile',
        'name': 'Inverted Profile Perspective (180° Pitch)',
        'rotate': 180,
        'flip_h': False,
        'gantry_tag': 'GANTRY-INV180'
    },
    {
        'id': 'yaw_30_tilt',
        'name': '30° Yaw Lateral Profile with Depth Focus',
        'rotate': -30,
        'flip_h': False,
        'gantry_tag': 'GANTRY-YAW30'
    },
    {
        'id': 'grazing_high_specular',
        'name': 'High-Specular Darkfield Grazing Angle',
        'rotate': 8,
        'flip_h': True,
        'gantry_tag': 'GANTRY-DARKF8'
    }
]

MODALITIES = [
    {
        'id': 'vis_clean',
        'name': 'Visible Light Macro (Golden Specimen)',
        'type': 'clean'
    },
    {
        'id': 'vis_defect',
        'name': 'Visible Light Macro (Defect Highlighted)',
        'type': 'defect'
    },
    {
        'id': 'thermal_flir',
        'name': 'FLIR False-Color Thermal Anomaly Heatmap',
        'type': 'thermal'
    },
    {
        'id': 'laser_contour',
        'name': 'Laser Profilometry Differential Contour',
        'type': 'contour'
    },
    {
        'id': 'xray_radiography',
        'name': 'BGA Radiography Solder Ball Penetration',
        'type': 'xray'
    }
]

def make_thermal(img):
    gray = img.convert('L')
    # Build JET colormap lookup table
    palette = []
    for i in range(256):
        v = i / 255.0
        if v < 0.25:
            r = 0
            g = int(4 * v * 255)
            b = 255
        elif v < 0.5:
            r = 0
            g = 255
            b = int((1 - 4 * (v - 0.25)) * 255)
        elif v < 0.75:
            r = int(4 * (v - 0.5) * 255)
            g = 255
            b = 0
        else:
            r = 255
            g = int((1 - 4 * (v - 0.75)) * 255)
            b = 0
        palette.extend((r, g, b))
    
    thermal_img = Image.new('P', gray.size)
    thermal_img.putpalette(palette)
    thermal_img.paste(gray, (0, 0))
    return thermal_img.convert('RGB')

def make_contour(img):
    edges = img.convert('L').filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(2.5)
    # Colorize cyan / electric blue
    cyan_mask = ImageOps.colorize(edges, black="#090D16", white="#38BDF8")
    return cyan_mask

def make_xray(img):
    gray = img.convert('L')
    inv = ImageOps.invert(gray)
    inv = ImageEnhance.Contrast(inv).enhance(1.8)
    # Tint deep metallic green/blue x-ray tone
    xray = ImageOps.colorize(inv, black="#04121F", white="#6EE7B7")
    return xray

def draw_hud(draw, width, height, comp, angle, modality, is_defect):
    # Border corner brackets
    bracket_len = 30
    bracket_color = (56, 189, 248) if not is_defect else (239, 68, 68)
    
    # Top-Left
    draw.line([(10, 10), (10 + bracket_len, 10)], fill=bracket_color, width=2)
    draw.line([(10, 10), (10, 10 + bracket_len)], fill=bracket_color, width=2)
    # Top-Right
    draw.line([(width - 10, 10), (width - 10 - bracket_len, 10)], fill=bracket_color, width=2)
    draw.line([(width - 10, 10), (width - 10, 10 + bracket_len)], fill=bracket_color, width=2)
    # Bottom-Left
    draw.line([(10, height - 10), (10 + bracket_len, height - 10)], fill=bracket_color, width=2)
    draw.line([(10, height - 10), (10, height - 10 - bracket_len)], fill=bracket_color, width=2)
    # Bottom-Right
    draw.line([(width - 10, height - 10), (width - 10 - bracket_len, height - 10)], fill=bracket_color, width=2)
    draw.line([(width - 10, height - 10), (width - 10, height - 10 - bracket_len)], fill=bracket_color, width=2)

    # Top Header Telemetry Box
    top_box_bg = (9, 13, 22, 210)
    draw.rectangle([(16, 16), (width - 16, 44)], fill=(12, 18, 30))
    draw.line([(16, 44), (width - 16, 44)], fill=(40, 56, 80), width=1)
    
    status_text = "STATUS: PASS (GOLDEN SPEC)" if not is_defect else "ANOMALY FLAGGED: CRITICAL EXCLUSION"
    status_col = (16, 185, 129) if not is_defect else (239, 68, 68)

    draw.text((24, 22), f"SMARTRMA VISION GANTRY • {angle['gantry_tag']}", fill=(248, 250, 252), font=FONT_SM)
    draw.text((width - 320, 22), status_text, fill=status_col, font=FONT_SM)

    # Crosshairs in Center
    cx, cy = width // 2, height // 2
    ch_col = (255, 255, 255, 120)
    draw.line([(cx - 15, cy), (cx + 15, cy)], fill=ch_col, width=1)
    draw.line([(cx, cy - 15), (cx, cy + 15)], fill=ch_col, width=1)
    draw.ellipse([(cx - 8, cy - 8), (cx + 8, cy + 8)], outline=ch_col, width=1)

    # Bottom Footer Telemetry
    draw.rectangle([(16, height - 52), (width - 16, height - 16)], fill=(12, 18, 30))
    draw.line([(16, height - 52), (width - 16, height - 52)], fill=(40, 56, 80), width=1)

    draw.text((24, height - 44), f"DUT: {comp['name']}", fill=(226, 232, 240), font=FONT_SM)
    draw.text((24, height - 30), f"MODALITY: {modality['name'].upper()} • SCALE: {comp['scale_mm']}mm/div", fill=(148, 163, 184), font=FONT_XS)

    # Scale bar in bottom right
    scale_w = 60
    sx = width - 120
    sy = height - 34
    draw.line([(sx, sy), (sx + scale_w, sy)], fill=(248, 250, 252), width=2)
    draw.line([(sx, sy - 4), (sx, sy + 4)], fill=(248, 250, 252), width=1)
    draw.line([(sx + scale_w, sy - 4), (sx + scale_w, sy + 4)], fill=(248, 250, 252), width=1)
    draw.text((sx + 8, sy - 14), f"{comp['scale_mm']*2:.1f}mm", fill=(248, 250, 252), font=FONT_XS)

    # If defect, draw localized bounding box
    if is_defect:
        bx1 = int(width * 0.45)
        by1 = int(height * 0.35)
        bx2 = int(width * 0.68)
        by2 = int(height * 0.62)
        draw.rectangle([(bx1, by1), (bx2, by2)], outline=(239, 68, 68), width=2)
        draw.rectangle([(bx1, by1 - 16), (bx1 + 130, by1)], fill=(239, 68, 68))
        draw.text((bx1 + 4, by1 - 14), "DEFECT: 0.88 PEAK", fill=(255, 255, 255), font=FONT_XS)

def generate_catalog():
    manifest = []
    generated_count = 0

    print("Generating comprehensive hardware inspection image catalog...")

    # We will generate combinations across components, angles, and modalities
    # Total count targeted: > 100 images
    for comp_idx, comp in enumerate(COMPONENTS):
        base_key = comp['base']
        if base_key not in loaded_bases:
            continue
        base_img = loaded_bases[base_key]
        bw, bh = base_img.size

        # Compute crop
        x1 = int(comp['crop_box'][0] * bw)
        y1 = int(comp['crop_box'][1] * bh)
        x2 = int(comp['crop_box'][2] * bw)
        y2 = int(comp['crop_box'][3] * bh)
        cropped = base_img.crop((x1, y1, x2, y2))

        # Select a subset of angles and modalities per component to get variety
        for ang_idx, angle in enumerate(ANGLES):
            for mod_idx, modality in enumerate(MODALITIES):
                # We want diverse coverage totaling over 100 images
                # 15 components * 8 angles * 5 modalities = 600 potential; let's sample systematically
                if (comp_idx + ang_idx + mod_idx) % 5 != 0 and (ang_idx != 0 and mod_idx != 0):
                    # Keep approximately 120 curated images
                    continue

                img = cropped.copy()

                # 1. Perspective / Rotation
                if angle['rotate'] != 0:
                    img = img.rotate(angle['rotate'], resample=Image.Resampling.BICUBIC, expand=True)
                if angle['flip_h']:
                    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

                # Resize to target
                img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

                is_defect = modality['type'] == 'defect' or (modality['type'] == 'thermal' and comp_idx % 2 == 1)

                # 2. Apply Modality Filters
                if modality['type'] == 'thermal':
                    img = make_thermal(img)
                elif modality['type'] == 'contour':
                    img = make_contour(img)
                elif modality['type'] == 'xray':
                    img = make_xray(img)
                elif modality['type'] == 'defect':
                    # Enhance contrast and add color aberration on defect
                    enh = ImageEnhance.Contrast(img).enhance(1.25)
                    img = enh

                # 3. Draw Telemetry Overlay
                draw = ImageDraw.Draw(img)
                draw_hud(draw, TARGET_SIZE[0], TARGET_SIZE[1], comp, angle, modality, is_defect)

                # 4. Save file
                generated_count += 1
                filename = f"rma_{generated_count:03d}_{comp['id']}_{angle['id']}_{modality['id']}.jpg"
                file_path = os.path.join(ASSETS_DIR, filename)

                img.save(file_path, quality=92)

                manifest.append({
                    "id": f"IMG-{generated_count:03d}",
                    "filename": filename,
                    "component_id": comp['id'],
                    "component_name": comp['name'],
                    "angle_id": angle['id'],
                    "angle_name": angle['name'],
                    "modality_id": modality['id'],
                    "modality_name": modality['name'],
                    "is_defect": is_defect,
                    "scale_mm": comp['scale_mm'],
                    "resolution": f"{TARGET_SIZE[0]}x{TARGET_SIZE[1]}"
                })

                if generated_count >= 115:
                    break
            if generated_count >= 115:
                break
        if generated_count >= 115:
            break

    # Save manifest.json
    manifest_path = os.path.join(ASSETS_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({
            "total_images": len(manifest),
            "generated_at": "2026-10-06T11:25:00Z",
            "camera_gantry": "SmartRMA Automated Robotic Inspection System v2.4",
            "images": manifest
        }, f, indent=2)

    print(f"Successfully generated {len(manifest)} hardware inspection images in {ASSETS_DIR}")
    print(f"Manifest catalog written to {manifest_path}")

if __name__ == '__main__':
    generate_catalog()

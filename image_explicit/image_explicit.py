import argparse
import json
import os
import sys
from io import BytesIO
import traceback  # 引入traceback模块用于详细的错误报告

import requests
from PIL import Image, ImageDraw, ImageFont

# 脚本将首先在'fonts'子目录中查找字体文件。
# 请将字体文件（如msyh.ttc, simsun.ttc等）放入该目录。
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')

# 如果在'fonts'目录中找不到，会尝试一些常见的系统路径
SYSTEM_FONT_PATHS = [
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', # 文泉驿正黑
    '/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc',
]

def find_font(font_name_key):
    """查找字体文件路径"""
    font_files = {
        1: "msyh.ttc",       # 微软雅黑
        2: "simsun.ttc",     # 宋体
        3: "simhei.ttf",     # 黑体
        4: "arial.ttf",      # Arial
        5: "times.ttf",      # Times New Roman
    }
    font_filename = font_files.get(font_name_key)
    if not font_filename:
        return None
    
    # 1. 检查 'fonts' 目录
    local_font_path = os.path.join(FONT_DIR, font_filename)
    if os.path.exists(local_font_path):
        return local_font_path

    # 2. 如果是微软雅黑等中文字体，尝试系统备用
    if font_name_key in [1, 2, 3]:
        for path in SYSTEM_FONT_PATHS:
            if os.path.exists(path):
                return path
    
    # 3. 对于英文字体，Pillow通常可以自己找到
    try:
        ImageFont.truetype(font_filename)
        return font_filename
    except IOError:
        pass

    return None


def get_default_explicit_label():
    """获取默认的水印参数"""
    return {
        'ContentMode': 3,          # 默认内容为 "AI生成"
        'PositionMode': 1,
        'TextDirection': 0,
        'TextScale': 0.08,
        'TextColor': [255, 255, 255],
        'FontName': 1,
        'Opacity': 1.0,
    }

def EmbedImageExplicitLabel(OriginalImagePath: str, ResultFilePath: str, ExplicitLabel: dict) -> str:
    """
    在图片上嵌入可视化水印文字,用于显示标识信息。
    """
    # --- Start Enhanced Debugging ---
    print("\n--- DEBUG INFO ---")
    print(f"CWD: {os.getcwd()}")
    print(f"__file__: {os.path.abspath(__file__)}")
    print(f"FONT_DIR: {FONT_DIR}")
    print(f"OriginalImagePath: '{OriginalImagePath}' (exists: {os.path.exists(OriginalImagePath)})")
    print(f"ResultFilePath: '{ResultFilePath}'")
    # --- End Enhanced Debugging ---

    try:
        # --- 1. 参数准备 ---
        defaults = get_default_explicit_label()
        label_config = defaults.copy()
        label_config.update(ExplicitLabel)

        # 新逻辑：根据 ContentMode 或 LableContent 确定水印文本
        content_options = {
            1: "人工智能生成",
            2: "人工智能合成",
            3: "AI生成",
            4: "AI合成",
        }
        
        content_mode = label_config.get('ContentMode')
        if content_mode in content_options:
            content = content_options[content_mode]
        else:
            # 向后兼容旧的 LableContent 参数，如果ContentMode不存在，则尝试使用LableContent
            content = label_config.get('LableContent', 'AI生成')

        position_mode = label_config['PositionMode']
        direction = label_config['TextDirection']
        scale = label_config['TextScale']
        color = tuple(label_config['TextColor'])
        font_name_key = label_config['FontName']
        opacity = label_config['Opacity']

        if not (0.0 <= opacity <= 1.0):
            return json.dumps({"status": -1, "result": "Opacity must be between 0.0 and 1.0."})
        if scale < 0.05:
            # 根据说明，TextScale 范围是 >= 0.05
            return json.dumps({"status": -1, "result": "TextScale must be >= 0.05"})

        # --- 2. 加载图片 ---
        if OriginalImagePath.startswith(('http://', 'https://')):
            response = requests.get(OriginalImagePath, timeout=10)
            response.raise_for_status()
            image_bytes = BytesIO(response.content)
            img = Image.open(image_bytes)
        else:
            if not os.path.exists(OriginalImagePath):
                return json.dumps({"status": -2, "result": f"Input image not found. os.path.exists failed for path: {OriginalImagePath}"})
            try:
                img = Image.open(OriginalImagePath)
            except FileNotFoundError:
                # 添加详细的路径信息以供调试
                return json.dumps({"status": -2, "result": f"Image.open could not find the image file. Absolute path checked: {os.path.abspath(OriginalImagePath)}"})
        
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # --- 3. 准备字体和文本 ---
        font_path = find_font(font_name_key)
        print(f"Font path search result: '{font_path}' (exists: {os.path.exists(font_path) if font_path else 'N/A'})")
        if not font_path:
            # 如果找不到任何指定字体，尝试找一个能用的默认字体
            font_path = find_font(1) or find_font(4)
            if not font_path:
                 return json.dumps({"status": -1, "result": f"Font for ID {font_name_key} not found. Please place fonts in a 'fonts' directory or install WenQuanYi Zen Hei."})

        img_width, img_height = img.size
        font_size = int(min(img_width, img_height) * scale)
        
        try:
            font = ImageFont.truetype(font_path, font_size)
        except (IOError, FileNotFoundError):
            return json.dumps({"status": -2, "result": f"Font file could not be opened or found. Path checked: {font_path}"})

        if direction == 1:  # 纵向
            content = '\n'.join(list(content))

        # --- 4. 计算文本位置 ---
        temp_draw = ImageDraw.Draw(Image.new("RGBA", (0,0)))
        try:
            # textbbox is preferred for more accurate bounding box
            _, top, _, bottom = temp_draw.textbbox((0, 0), content, font=font)
            text_width = temp_draw.textlength(content, font=font)
            text_height = bottom - top
        except AttributeError:
            # Fallback for older Pillow versions
            text_width, text_height = temp_draw.textsize(content, font=font)

        margin = int(font_size * 0.5) # 边距, 从 0.2 增加到 0.5

        positions = {
            1: (img_width - text_width - margin, img_height - text_height - margin), # 右下
            2: (margin, img_height - text_height - margin), # 左下
            3: (img_width - text_width - margin, margin), # 右上
            4: (margin, margin), # 左上
            -1: ((img_width - text_width) // 2, img_height - text_height - margin), # 下中
            -2: ((img_width - text_width) // 2, margin), # 上中
            -3: (margin, (img_height - text_height) // 2), # 左中
            -4: (img_width - text_width - margin, (img_height - text_height) // 2), # 右中
        }
        x, y = positions.get(position_mode, positions[1])

        # --- 5. 创建水印层并绘制 ---
        watermark_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        text_color_with_opacity = color + (int(255 * opacity),)
        draw.text((x, y), content, font=font, fill=text_color_with_opacity)

        # --- 6. 合成并保存 ---
        result_img = Image.alpha_composite(img, watermark_layer)
        
        output_format = ResultFilePath.split('.')[-1].upper()
        if output_format in ['JPG', 'JPEG']:
            result_img = result_img.convert('RGB')

        # 修复：只有在目录名非空时才创建目录
        output_dir = os.path.dirname(ResultFilePath)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
        result_img.save(ResultFilePath)

        return json.dumps({"status": 1, "result": f"Successfully watermarked image and saved to {ResultFilePath}"}, ensure_ascii=False)

    except requests.exceptions.RequestException as e:
        return json.dumps({"status": -2, "result": f"Network error fetching image: {e}"}, ensure_ascii=False)
    except FileNotFoundError:
        # 这个通用的捕获理论上不应该再被触发，但保留以防万一
        return json.dumps({"status": -2, "result": "An unexpected FileNotFoundError occurred. Please check file paths.", "traceback": traceback.format_exc()}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": -2, "result": f"An unexpected error occurred: {e}", "traceback": traceback.format_exc()}, ensure_ascii=False)

def main():
    """主函数，用于解析命令行参数"""
    parser = argparse.ArgumentParser(description='Embed a watermark on an image.', formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('OriginalImagePath', type=str, help='Path or URL to the original image.')
    parser.add_argument('ResultFilePath', type=str, help='Output path for the watermarked image.')
    
    # --- 水印详细参数 ---
    label_help = """
Watermark settings in JSON format. Example:
'{"ContentMode": 1, "PositionMode": 3, "Opacity": 0.8}'

Settable fields (with defaults):
  'ContentMode': 3                 // int, Watermark Content. 1:"人工智能生成", 2:"人工智能合成", 3:"AI生成", 4:"AI合成".
  'LableContent': 'AI生成'         // str, DEPRECATED. Use ContentMode instead.
  'PositionMode': 1                // int, Position: 1(BR), 2(BL), 3(TR), 4(TL), -1(BC), -2(TC), -3(LC), -4(RC)
  'TextDirection': 0               // int, Direction: 0(Horizontal), 1(Vertical)
  'TextScale': 0.08                // float, Text height ratio to image's shorter side (>= 0.05)
  'TextColor': [0, 0, 0]           // list, RGB color (e.g., [255, 0, 0] for red)
  'FontName': 1                    // int, Font: 1(MS YaHei), 2(Simsun), 3(Heiti), 4(Arial), 5(Times New Roman)
  'Opacity': 0.5                   // float, Opacity from 0.0 (transparent) to 1.0 (opaque)
"""
    parser.add_argument('--ExplicitLabel', type=str, default='{}', help=label_help)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
        
    args = parser.parse_args()

    try:
        explicit_label_dict = json.loads(args.ExplicitLabel)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format for --ExplicitLabel: {args.ExplicitLabel}", file=sys.stderr)
        sys.exit(1)

    result_json = EmbedImageExplicitLabel(args.OriginalImagePath, args.ResultFilePath, explicit_label_dict)
    print(result_json)

if __name__ == "__main__":
    main() 
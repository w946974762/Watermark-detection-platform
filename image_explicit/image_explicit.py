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
        'LableContent': 3,          # 默认内容模式为 3 ("AI生成")
        'PositionMode': 1,
        'TextDirection': 0,
        'TextScale': 0.08,
        'TextColor': [255, 255, 255],
        'FontName': 1,
        'Opacity': 1.0,
    }

def is_chinese(char):
    """检查字符是否为中文字符"""
    return '\u4e00' <= char <= '\u9fff'

def _segment_text(text, special_word="AI"):
    """
    将文本分割成中英文片段。特殊处理 "AI" 作为一个整体。
    """
    segments = []
    if not text:
        return segments
    
    # 将文本按 "AI" 分割，保留 "AI"
    parts = text.split(special_word)
    for i, part in enumerate(parts):
        if part:
            # "AI" 前后的部分，我们仍按常规中英文分割
            current_segment = ""
            if not part: continue
            is_last_char_chinese = is_chinese(part[0])
            for char in part:
                current_char_is_chinese = is_chinese(char)
                if current_char_is_chinese == is_last_char_chinese:
                    current_segment += char
                else:
                    segments.append((current_segment, is_last_char_chinese))
                    current_segment = char
                    is_last_char_chinese = current_char_is_chinese
            segments.append((current_segment, is_last_char_chinese))

        # 在分割点插入 "AI" 片段
        if i < len(parts) - 1:
            segments.append((special_word, False)) # "AI" is not Chinese
            
    return segments

def get_mixed_text_dimensions(draw, text, english_font, chinese_font):
    """计算混合字体文本的总尺寸，能处理横向与纵向。"""
    lines = text.split('\n')
    max_line_width = 0
    total_height = 0

    if len(lines) > 1:  # 纵向文本模式
        vertical_line_spacing_factor = 0.9
        # 使用较大的字体大小作为基准行高
        base_line_height = max(english_font.size, chinese_font.size) * vertical_line_spacing_factor

        for line in lines:
            segments = _segment_text(line)
            current_line_width = 0
            for segment, is_chinese_seg in segments:
                font = chinese_font if is_chinese_seg else english_font
                current_line_width += draw.textlength(segment, font=font)
            
            if current_line_width > max_line_width:
                max_line_width = current_line_width
            
            total_height += base_line_height
    else:  # 单行横向文本模式
        segments = _segment_text(text)
        line_max_ascent = 0
        line_max_descent = 0
        for segment, is_chinese_seg in segments:
            font = chinese_font if is_chinese_seg else english_font
            max_line_width += draw.textlength(segment, font=font)
            ascent, descent = font.getmetrics()
            if ascent > line_max_ascent:
                line_max_ascent = ascent
            if descent > line_max_descent:
                line_max_descent = descent
        total_height = line_max_ascent + line_max_descent

    return max_line_width, total_height

def draw_mixed_text(draw, position, text, english_font, chinese_font, fill):
    """在指定位置绘制混合字体的文本，处理基线对齐和纵向文本。"""
    x, y = position

    # 统一计算绘制时所需的基线信息
    eng_ascent, _ = english_font.getmetrics()
    cn_ascent, _ = chinese_font.getmetrics()
    max_ascent = max(eng_ascent, cn_ascent)

    if '\n' in text: # 纵向文本模式
        lines = text.split('\n')
        current_y = y
        
        vertical_line_spacing_factor = 0.9
        line_increment = max(english_font.size, chinese_font.size) * vertical_line_spacing_factor

        for line in lines:
            # --- 开始绘制单行（此处为单个纵向字符） ---
            current_x_inner = x
            segments = _segment_text(line)
            for segment, is_segment_chinese in segments:
                font = chinese_font if is_segment_chinese else english_font
                segment_ascent, _ = font.getmetrics()
                # 基于统一的基线调整每个片段的垂直位置
                draw_y = current_y + (max_ascent - segment_ascent)
                draw.text((current_x_inner, draw_y), segment, font=font, fill=fill)
                current_x_inner += draw.textlength(segment, font=font)
            # --- 单行绘制结束 ---
            
            current_y += line_increment # 使用计算好的固定行高进行递增
        return

    # --- 单行横向文本模式 ---
    current_x = x
    segments = _segment_text(text)
    for segment, is_segment_chinese in segments:
        font = chinese_font if is_segment_chinese else english_font
        # 基于统一的基线调整每个片段的垂直位置
        segment_ascent, _ = font.getmetrics()
        draw_y = y + (max_ascent - segment_ascent)
        
        draw.text((current_x, draw_y), segment, font=font, fill=fill)
        current_x += draw.textlength(segment, font=font)


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

        # 新逻辑：LableContent 支持整数模式和直接的字符串输入
        content_options = {
            1: "人工智能生成",
            2: "人工智能合成",
            3: "AI生成",
            4: "AI合成",
        }
        
        content_input = label_config.get('LableContent')
        
        content = ''
        if isinstance(content_input, int) and content_input in content_options:
            # 如果是有效的整数模式，获取对应的文本
            content = content_options[content_input]
        elif isinstance(content_input, str):
            # 如果是字符串，直接使用
            content = content_input
        else:
            # 对于其他无效输入或没有输入，回退到默认值
            # 兼容旧的ContentMode
            content = label_config.get('ContentMode', content_options[get_default_explicit_label()['LableContent']])

        position_mode = label_config['PositionMode']
        direction = label_config['TextDirection']
        scale = label_config['TextScale']
        color = tuple(label_config['TextColor'])
        font_name_key = label_config['FontName']
        opacity = label_config['Opacity']

        # 检查是否需要特殊处理字体4/5
        use_mixed_render = False
        if font_name_key in [4, 5]:
            if "AI" in content:
                use_mixed_render = True
            else:
                # 不含 "AI" 但选了英文字体，直接回退到默认中文字体
                font_name_key = 1

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

        # --- 3 & 4. 字体准备、位置计算 ---
        img_width, img_height = img.size
        font_size = int(min(img_width, img_height) * scale)
        if direction == 1:  # 纵向
            # 特殊处理纵向文本，让 "AI" 保持在同一行，而不是垂直分开
            new_content_parts = []
            i = 0
            while i < len(content):
                if content[i:i+2] == 'AI':
                    new_content_parts.append('AI')
                    i += 2
                else:
                    new_content_parts.append(content[i])
                    i += 1
            content = '\n'.join(new_content_parts)

        temp_draw = ImageDraw.Draw(Image.new("RGBA", (0,0)))

        if use_mixed_render:
            eng_font_path = find_font(font_name_key)
            cn_font_path = find_font(1) # 默认中文设为微软雅黑
            if not eng_font_path or not cn_font_path:
                return json.dumps({"status": -1, "result": f"Could not find required fonts for mixed rendering. English: {eng_font_path}, Chinese: {cn_font_path}"})
            
            try:
                english_font = ImageFont.truetype(eng_font_path, font_size)
                chinese_font = ImageFont.truetype(cn_font_path, font_size)
            except (IOError, FileNotFoundError):
                return json.dumps({"status": -2, "result": "A font file for mixed rendering could not be opened."})
            
            text_width, text_height = get_mixed_text_dimensions(temp_draw, content, english_font, chinese_font)
        else:
            font_path = find_font(font_name_key)
            print(f"Font path search result: '{font_path}' (exists: {os.path.exists(font_path) if font_path else 'N/A'})")
            if not font_path:
                font_path = find_font(1) or find_font(4)
                if not font_path:
                     return json.dumps({"status": -1, "result": f"Font for ID {font_name_key} not found. Please place fonts in a 'fonts' directory."})

            try:
                font = ImageFont.truetype(font_path, font_size)
            except (IOError, FileNotFoundError):
                return json.dumps({"status": -2, "result": f"Font file could not be opened or found. Path checked: {font_path}"})
            
            try:
                # 使用 textbbox 来同时计算宽度和高度，该方法能正确处理多行文本
                left, top, right, bottom = temp_draw.textbbox((0, 0), content, font=font)
                text_width = right - left
                text_height = bottom - top
            except AttributeError:
                # 为旧版Pillow保留的回退方法，可能对多行文本支持不佳
                text_width, text_height = temp_draw.textsize(content, font=font)

        margin = int(font_size * 0.5)

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
        
        if use_mixed_render:
            draw_mixed_text(draw, (x, y), content, english_font, chinese_font, text_color_with_opacity)
        else:
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
'{"LableContent": 1, "PositionMode": 3, "Opacity": 0.8}'
'{"LableContent": "自定义文本", "PositionMode": 3, "Opacity": 0.8}'

Settable fields (with defaults):
  'LableContent': 3                // int|str, (Recommended) Watermark content.
                                     // Use int mode for presets to avoid encoding issues: 1:"...", 2:"...", 3:"...", 4:"...".
                                     // Or provide a direct string.
  'PositionMode': 1                // int, Position: 1(BR), 2(BL), 3(TR), 4(TL), -1(BC), -2(TC), -3(LC), -4(RC)
  'TextDirection': 0               // int, Direction: 0(Horizontal), 1(Vertical)
  'TextScale': 0.08                // float, Text height ratio to image's shorter side (>= 0.05)
  'TextColor': [0, 0, 0]           // list, RGB color (e.g., [255, 0, 0] for red)
  'FontName': 1                    // int, Font: 1(MS YaHei), 2(Simsun), 3(Heiti), 4(Arial), 5(Times New Roman)
  'Opacity': 0.5                   // float, Opacity from 0.0 (transparent) to 1.0 (opaque)
  'ContentMode': 'AI生成'          // str, (DEPRECATED) Use LableContent instead.
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
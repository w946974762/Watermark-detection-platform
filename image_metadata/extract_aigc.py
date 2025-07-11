#!/usr/bin/env python
import json
import argparse
import piexif
import pillow_heif
from PIL import Image

# 确保 HEIF/HEIC 格式被支持
pillow_heif.register_heif_opener()

def read_exif_user_comment(image_path):
    """
    使用 piexif 读取并解析 UserComment 字段。
    """
    try:
        img = Image.open(image_path)
        
        # piexif 需要原始的 exif 字节数据
        exif_data = img.info.get('exif')
        if not exif_data:
            print("图片不包含任何 EXIF 数据。")
            return None

        exif_dict = piexif.load(exif_data)
        
        # 获取 UserComment 的原始字节
        user_comment_bytes = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)

        if not user_comment_bytes:
            print("EXIF 中未找到 UserComment 字段。")
            return None

        # 解析编码前缀
        try:
            # 编码信息在头8个字节
            encoding = user_comment_bytes[:8].decode('ascii').rstrip('\0')
            
            # 遵从参考示例, 使用 split(b'\x00',1)[0] 来精确提取内容
            if encoding == 'ASCII':
                comment = user_comment_bytes[8:].split(b'\x00',1)[0].decode('ascii')
            elif encoding == 'UNICODE':
                # UNICODE 编码本身处理结尾, split 可能不是最佳选择
                comment = user_comment_bytes[8:].decode('utf-16').rstrip('\x00')
            else:
                # 如果编码未知，则尝试用 ASCII 解码
                print(f"警告: 未知的编码格式 '{encoding}'，将尝试用 ASCII 解码。")
                comment = user_comment_bytes[8:].split(b'\x00',1)[0].decode('ascii', errors='ignore')

            return comment

        except Exception as e:
            print(f"解析 UserComment 字节时出错: {e}")
            return None

    except FileNotFoundError:
        print(f"错误: 文件未找到 -> {image_path}")
        return None
    except Exception as e:
        print(f"读取图片时发生未知错误: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="检测并提取图片 EXIF UserComment 字段中的AIGC隐式标识。")
    parser.add_argument("image_path", help="要检查的图片路径。")
    args = parser.parse_args()

    print(f"--- 正在分析图片: {args.image_path} ---")
    user_comment_json = read_exif_user_comment(args.image_path)

    if user_comment_json:
        print("成功提取 UserComment 内容。")
        try:
            # 解析JSON并美化输出
            data = json.loads(user_comment_json)
            print("\n--- 检测结果: 找到 AIGC 标识 ---")
            print(json.dumps(data, indent=4, ensure_ascii=False))
        except json.JSONDecodeError:
            print("\n--- 检测结果: 找到的 UserComment 内容不是有效的 JSON 格式 ---")
            print(user_comment_json)
    else:
        print("\n--- 检测结果: 未找到或无法解析 AIGC 标识 ---")


if __name__ == "__main__":
    main() 
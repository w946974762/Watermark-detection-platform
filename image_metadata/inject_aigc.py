import json
import argparse
import piexif
import pillow_heif
from PIL import Image

# 确保 HEIF/HEIC 格式被支持
pillow_heif.register_heif_opener()

def make_user_comment_bytes(comment, encoding="ascii"):
    """
    根据 EXIF 规范创建 UserComment 的字节数据。
    """
    if encoding.lower() == "ascii":
        # 8字节前缀 + 内容
        prefix = b'ASCII\x00\x00\x00'
        return prefix + comment.encode('ascii')
    elif encoding.lower() == "unicode":
        prefix = b'UNICODE\x00'
        return prefix + comment.encode('utf-16-be')
    else:
        raise ValueError("不支持的编码格式")

def write_to_exif_user_comment(input_path, output_path, aigc_json_str):
    """
    使用 piexif 将 AIGC 数据写入 UserComment 字段。
    """
    try:
        # 打开原始图片
        img = Image.open(input_path)

        # 构造 EXIF 字典
        comment_bytes = make_user_comment_bytes(aigc_json_str)
        exif_dict = {"Exif": {piexif.ExifIFD.UserComment: comment_bytes}}
        exif_bytes = piexif.dump(exif_dict)

        # 保存图片并写入 EXIF
        # 需要保留原始图片的质量和格式信息
        params = {"quality": -1}
        if img.format:
             params['format'] = img.format
        img.save(output_path, exif=exif_bytes, **params)
        
        print(f"成功将标识注入到图片: {output_path}")

    except FileNotFoundError:
        print(f"错误: 输入文件未找到 -> {input_path}")
    except Exception as e:
        print(f"处理图片时发生未知错误: {e}")

def main():
    default_aigc = {
        "Label": "1",
        "ContentProducer": "1565201000000016BDWXYY0400000000",
        "ProduceID": "v0300fg100kbc3e77ub10123456",
        "ReserveCode1": "e862483430d978cbf828b8b24296ef9328d843a0",
        "Propagator": "1561101000000057WMWB030000000000",
        "PropatorID": "qdn57u6mld93z6o1xvz",
        "ReserveCode2": "e862483430d978cbf828b8b24296ef9328d843a0"
    }
    # 根据您的示例，AIGC数据需要被包在一个顶层 "AIGC" 键中
    aigc_data_wrapped = {'AIGC': default_aigc}
    default_aigc_str = json.dumps(aigc_data_wrapped)

    parser = argparse.ArgumentParser(description="向AI生成的图片的EXIF UserComment字段注入隐式AIGC标识。")
    parser.add_argument("input_image", help="输入的原始图片路径。")
    parser.add_argument("output_image", help="注入标识后保存的新图片路径。")
    parser.add_argument("--aigc_json", default=default_aigc_str,
                        help=f"要注入的AIGC元数据 (JSON格式字符串)。")

    args = parser.parse_args()

    write_to_exif_user_comment(args.input_image, args.output_image, args.aigc_json)


if __name__ == "__main__":
    main() 
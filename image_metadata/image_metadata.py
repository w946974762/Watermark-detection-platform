import json
import piexif
import pillow_heif
import requests
import tempfile
import os
from PIL import Image

# 确保 HEIF/HEIC 格式被支持
pillow_heif.register_heif_opener()

# --- 辅助函数 ---

def _download_image(url):
    """从URL下载图片到临时文件，并返回文件路径"""
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        # 使用 tempfile 创建一个安全的临时文件
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        for chunk in response.iter_content(chunk_size=8192):
            temp_file.write(chunk)
        
        temp_path = temp_file.name
        temp_file.close()
        return temp_path
    except requests.RequestException as e:
        raise IOError(f"下载图片失败: {e}")

def _make_user_comment_bytes(comment, encoding="ascii"):
    """根据 EXIF 规范创建 UserComment 的字节数据"""
    if encoding.lower() == "ascii":
        prefix = b'ASCII\x00\x00\x00'
        return prefix + comment.encode('ascii')
    # ... 其他编码可以按需添加
    raise ValueError(f"不支持的编码格式: {encoding}")

def _read_user_comment(image_path):
    """使用 piexif 读取并解析 UserComment 字段"""
    img = Image.open(image_path)
    exif_data = img.info.get('exif')
    if not exif_data:
        return None
    
    exif_dict = piexif.load(exif_data)
    user_comment_bytes = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
    if not user_comment_bytes:
        return None
        
    try:
        encoding = user_comment_bytes[:8].decode('ascii').rstrip('\0')
        if encoding == 'ASCII':
            return user_comment_bytes[8:].split(b'\x00', 1)[0].decode('ascii')
        if encoding == 'UNICODE':
             return user_comment_bytes[8:].decode('utf-16').rstrip('\x00')
        # 对于未知编码，尝试解码
        return user_comment_bytes[8:].split(b'\x00', 1)[0].decode('ascii', errors='ignore')
    except Exception:
        return None


# --- API 接口函数 ---

def EmbedImageImplicitLabel(OriginalImagePath: str, ImplicitLabel: str, ResultFilePath: str) -> str:
    """
    将隐式标识信息嵌入至图片的元数据中，并输出处理结果的 JSON 字符串。
    """
    temp_path_for_input = None
    try:
        # 1. 处理输入路径 (URL 或本地)
        if OriginalImagePath.startswith(('http://', 'https://')):
            input_path = temp_path_for_input = _download_image(OriginalImagePath)
        else:
            input_path = OriginalImagePath

        # 2. 验证并构造最终要写入的JSON
        try:
            parsed_label = json.loads(ImplicitLabel)
        except json.JSONDecodeError:
            return json.dumps({"status": -2, "result": "执行错误: ImplicitLabel 不是有效的JSON字符串。"})
        
        aigc_data_to_write = json.dumps({'AIGC': parsed_label})

        # 3. 写入 EXIF
        img = Image.open(input_path)
        comment_bytes = _make_user_comment_bytes(aigc_data_to_write)
        exif_dict = {"Exif": {piexif.ExifIFD.UserComment: comment_bytes}}
        exif_bytes = piexif.dump(exif_dict)
        
        params = {"quality": -1}
        if img.format:
             params['format'] = img.format
        img.save(ResultFilePath, exif=exif_bytes, **params)
        
        return json.dumps({"status": 1, "result": "嵌入成功"})

    except FileNotFoundError:
        return json.dumps({"status": -2, "result": "执行错误: 原始图片文件未找到。"})
    except IOError as e: # 处理下载或文件读写错误
        return json.dumps({"status": -2, "result": f"执行错误: {e}"})
    except Exception as e:
        return json.dumps({"status": -1, "result": f"嵌入失败: {e}"})
    finally:
        # 清理临时文件
        if temp_path_for_input and os.path.exists(temp_path_for_input):
            os.remove(temp_path_for_input)


def DetectImageImplicitLabel(OriginalImagePath: str) -> str:
    """
    检测图片文件元数据中嵌入的隐式标识信息。
    """
    temp_path_for_input = None
    try:
        # 1. 处理输入路径 (URL 或本地)
        if OriginalImagePath.startswith(('http://', 'https://')):
            input_path = temp_path_for_input = _download_image(OriginalImagePath)
        else:
            input_path = OriginalImagePath

        # 2. 读取 UserComment
        user_comment = _read_user_comment(input_path)
        if not user_comment:
            return json.dumps({"status": -1, "result": "未检测到隐式标识"})

        # 3. 解析并验证 AIGC 结构
        data = json.loads(user_comment)
        aigc_content = data.get('AIGC')
        if not isinstance(aigc_content, dict):
            return json.dumps({"status": -1, "result": "未检测到有效的 AIGC 结构"})

        # 4. 构建三元组结果
        # “是否合规”的规则定义为：值不能为空字符串
        expected_keys = ["Label", "ContentProducer", "ProduceID", "ReservedCode1", 
                           "ContentPropagator", "PropagateID", "ReservedCode2"]
        result_label = []
        for key in expected_keys:
            value = aigc_content.get(key, "")
            is_compliant = bool(value) # 简单规则: 值不为空即合规
            result_label.append([key, str(value), is_compliant])

        return json.dumps({
            "status": 1,
            "result": "检测成功",
            "ImplicitLabel": result_label
        }, ensure_ascii=False)

    except FileNotFoundError:
        return json.dumps({"status": -2, "result": "执行错误: 图片文件未找到。"})
    except json.JSONDecodeError:
         return json.dumps({"status": -1, "result": "未检测到隐式标识: UserComment 内容不是有效的 JSON"})
    except IOError as e:
        return json.dumps({"status": -2, "result": f"执行错误: {e}"})
    except Exception as e:
        return json.dumps({"status": -2, "result": f"执行错误: {e}"})
    finally:
        # 清理临时文件
        if temp_path_for_input and os.path.exists(temp_path_for_input):
            os.remove(temp_path_for_input)

# --- 用于直接运行测试的示例 ---
if __name__ == '__main__':
    # 创建一个假的图片文件用于测试
    test_image_path = "test_image.png"
    Image.new('RGB', (100, 100), color = 'red').save(test_image_path)
    
    print("--- 测试嵌入功能 ---")
    label_to_embed = json.dumps({
         "Label": "value1",
         "ContentProducer": "value2",
         "ProduceID": "value3",
         "ReservedCode1": "value4",
         "ContentPropagator": "value5",
         "PropagateID": "value6",
         "ReservedCode2": "" # 测试一个空值
    })
    output_path = "output_image.png"
    result_embed = EmbedImageImplicitLabel(test_image_path, label_to_embed, output_path)
    print(result_embed)

    print("\n--- 测试检测功能 (成功案例) ---")
    result_detect_ok = DetectImageImplicitLabel(output_path)
    print(json.dumps(json.loads(result_detect_ok), indent=2, ensure_ascii=False))

    print("\n--- 测试检测功能 (失败案例) ---")
    result_detect_fail = DetectImageImplicitLabel(test_image_path)
    print(json.dumps(json.loads(result_detect_fail), indent=2, ensure_ascii=False))
    
    # 清理测试文件
    os.remove(test_image_path)
    os.remove(output_path) 
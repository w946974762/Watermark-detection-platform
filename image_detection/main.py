import sys
import os
import easyocr
from .judge_content import judge_content
from .judge_position import judge_position
import json

def DetectImageExplicitLabel(OriginalImagePath: str) -> str:
    """
    检测图片中已嵌入的显示标识信息。
    返回显示内容、位置、尺寸等信息的三元组结构，并判断是否合规。

    参数：
        OriginalImagePath (str): 图片文件路径，支持本地路径或 URL。
    返回：
        str: JSON 字符串，格式如下：
        {
            "status": 1 | -1 | -2, // 1: 检测成功, -1: 未检测到, -2: 执行错误
            "result": "检测说明",
            "ExplicitLabel": [
                ["LableContent", "AI生成", true],
                ["PositionMode", 1, true], // 1(右下), 2(左下), ...
                ["TextScale", 0.05, true]
            ]
        }
    """
    try:
        print(f"处理图片: {OriginalImagePath}")
        if not os.path.exists(OriginalImagePath):
            return json.dumps({
                "status": -2,
                "result": f"执行错误: 文件不存在 '{OriginalImagePath}'"
            })

        # 用中英文模型识别
        reader_cn = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        results_cn = reader_cn.readtext(OriginalImagePath)
        # 用英文模型识别
        reader_en = easyocr.Reader(['en'], gpu=False)
        results_en = reader_en.readtext(OriginalImagePath)
        # 合并所有文本内容（去重）
        all_results = results_cn + results_en
        texts = []
        bboxes = []
        for item in all_results:
            if item[1] not in texts:
                texts.append(item[1])
                bboxes.append(item[0])
        if not texts:
            return json.dumps({
                "status": -1,
                "result": "未检测到显式标识"
            })

        print("检测到的所有文本内容：")
        for i, text in enumerate(texts):
            print(f"  区域{i+1}: {text}")

        # 判断内容
        result = judge_content(texts)
        if result == "错误标识":
            return json.dumps({
                "status": -1,
                "result": "检测到非法标识内容"
            })
        print(f"\n检测到的显式标识内容：{result}")

        # 获取对应位置
        idx = texts.index(result)
        bbox = bboxes[idx]
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        x, y, w, h = int(min(x_coords)), int(min(y_coords)), int(max(x_coords)-min(x_coords)), int(max(y_coords)-min(y_coords))

        # 判断位置
        pos_result = judge_position(OriginalImagePath, (x, y, w, h))
        print(pos_result)

        # 构造返回结果
        return json.dumps({
            "status": 1,
            "result": "检测成功",
            "ExplicitLabel": [
                ["LableContent", result, True],
                ["PositionMode", pos_result.get('PositionMode', 0), True],
                ["TextScale", round(h / min(os.path.getsize(OriginalImagePath), 1000), 2), True]
            ]
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": -2,
            "result": f"执行错误: {str(e)}"
        })

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python main.py <图片路径>")
        sys.exit(1)
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print("图片文件不存在")
        sys.exit(1)
    process_image(image_path) 
    
    
    import sys

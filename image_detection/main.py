import sys
import os
# import easyocr
import cv2
from .judge_content import judge_content
from .judge_position import judge_position
import json
import numpy as np
from .paddle_test import paddle_test
import traceback


def pad_image(img, padding=20): 
    return cv2.copyMakeBorder(img, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=(0, 0, 0))

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
        # 预处理图片
        pre_img = cv2.imread(OriginalImagePath)  # 用彩色图识别
        # pre_img = preprocess_image(image_path)
        pre_img = pad_image(pre_img)
        # 用PaddleOCR识别，texts, bboxes为paddle_test返回结果
        texts, bboxes = paddle_test(OriginalImagePath)
        print("识别内容：", texts)
        # print("检测到的所有文本内容：")
        # for i, text in enumerate(texts):
        #     print(f"  区域{i+1}: {text}")


         # 判断内容
        idx, result, norm_result, status = judge_content(texts)
        if status=="检测到错误标识内容" or status=="没有检测到标识":
            return json.dumps({
                "status": -1,
                "result": status,
                "ExplicitLabel": [
                    ["LableContent", None, False],
                    ["PositionMode", None, False],
                    ["TextScale", None, False]
                ]
            })
        print(norm_result)

        # 获取对应位置
        idx = 0  # 默认取第一个识别结果
        bbox = bboxes[idx]
        # bbox为[x_min, y_min, x_max, y_max]
        x_min, y_min, x_max, y_max = bbox
        h = y_max - y_min
        # 获取图片尺寸，计算TextScale为字体高度与图片最短边的比例
        img = cv2.imread(OriginalImagePath)
        H, W = img.shape[:2]
        min_side = min(H, W)
        text_scale = round(h / min_side, 2) if min_side > 0 else 0
        print("TextScale:", text_scale)
        x = x_min
        y = y_min
        w = x_max - x_min
        h = y_max - y_min

        # 判断位置
        pos_result = judge_position(OriginalImagePath, (x, y, w, h))
        position_mode = pos_result.get('PositionMode', 0)
        print("position_mode", position_mode)
        # 在status后面添加位置判断文字、
        if status == "合格":
            if position_mode >= 0:
                status = status + "位置正确"
            else:
                status = status + "位置错误"
                # position_mode = None
        else:
            position_mode = None
            status = "检测到错误标识内容"

        output = {
                "status": 1,
                "result": status,
                "ExplicitLabel": [
                    ["LableContent", norm_result, True],
                    ["PositionMode", position_mode, True],
                    ["TextScale", text_scale, True]
                ]
            }
        print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
        # output = {
        #         "status": -1,
        #         "result": status,
        #         "ExplicitLabel": [
        #             ["LableContent", norm_result, False],
        #             ["PositionMode", position_mode, False],
        #             ["TextScale", None, False]
        #         ]
        #     }

        # print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)

        if status=="合格位置错误":
            return json.dumps({
                "status": -1,
                "result": status,
                "ExplicitLabel": [
                    ["LableContent", norm_result, True],
                    ["PositionMode", position_mode, False],
                    ["TextScale", text_scale, True]
                ]
            })
            
        if status=="合格位置正确":
            return json.dumps({
                "status": 1,
                "result": status,
                "ExplicitLabel": [
                    ["LableContent", norm_result, True],
                    ["PositionMode", position_mode, True],
                    ["TextScale", text_scale, True]
                ]
            }, ensure_ascii=False)
                    

        if status=="没有检测到标识" or status=="检测到错误标识内容":
            return json.dumps({
                "status": -1,
                "result": status,
                "ExplicitLabel": [
                    ["LableContent", norm_result, False],
                    ["PositionMode", position_mode, False],
                    ["TextScale", None, False]
                ]
            })
        
        # print(f"\n检测到的显式标识内容：{norm_result}")

        # 打印 JSON 格式字符串
        # # 构建输出字典
        # output = {
        #     "status": 1,
        #     "result": "检测成功",
        #     "ExplicitLabel": [
        #         ["LableContent", norm_result, True],
        #         ["PositionMode", pos_result.get('PositionMode', 0), True],
        #         ["TextScale", round(h / min(os.path.getsize(OriginalImagePath), 1000), 2), True]
        #     ]
        # }

        # print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)

    except Exception as e:
        return json.dumps({
            "status": -2,
            "result": f"执行错误: {str(traceback.format_exc())}"
        })

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python main.py <图片路径>")
        sys.exit(1)
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print("图片文件不存在")
        sys.exit(1)

    #process_image(image_path) 
    DetectImageExplicitLabel(image_path)
    # process_image(image_path)
    
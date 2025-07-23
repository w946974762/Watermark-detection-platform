import sys
import os
# import easyocr
import cv2
from .judge_content import judge_content
from .judge_position import judge_position
import json
import numpy as np
from .paddle_test import paddle_test
from paddleocr import PaddleOCR
import paddle


# 全局OCR实例
ocr_instance = None

def pad_image(img, padding=20): 
    return cv2.copyMakeBorder(img, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=(0, 0, 0))

def DetectImageExplicitLabel(OriginalImagePath: str) -> str:
    """
    检测图片中已嵌入的显示标识信息。
    返回显示内容、位置、尺寸等信息的三元组结构，并判断是否合规。

    参数：
        OriginalImagePath (str): 图片文件路径，支持本地路径或 URL。
        ocr_engine: 初始化后的PaddleOCR实例。
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
    # 在主程序中只初始化一次PaddleOCR
    print("正在初始化PaddleOCR模型，请稍候...")
    # PaddleOCR v2.6+ 会自动检测GPU环境，无需手动指定 use_gpu
    # 如果 paddlepaddle-gpu 安装正确，会自动使用GPU
    try:
        # 移除 show_log 参数, 并将 use_angle_cls 替换为 use_textline_orientation
        ocr_instance = PaddleOCR(use_textline_orientation=True, lang='ch', use_gpu=False)
        
        # # 检查PaddleOCR实际使用的设备
        # if paddle.is_compiled_with_cuda():
        #      print("模型初始化完成，使用 GPU。")
        # else:
        #      print("模型初始化完成，使用 CPU。")

    except Exception as e:
        print(f"模型初始化失败: {e}")
        sys.exit(1)

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
        texts, bboxes = paddle_test(ocr_instance, OriginalImagePath)
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

        # 初始化输出变量
        lable_content = None
        position_mode = None
        text_scale = None
        final_status_code = -1 # 默认为不合格
        content_ok = False
        position_ok = False
        scale_ok = False

        if status == "合格":
            content_ok = True
            lable_content = norm_result
            # 获取对应位置
            bbox = bboxes[idx]
            # bbox为[x_min, y_min, x_max, y_max]
            x_min, y_min, x_max, y_max = bbox
            h = y_max - y_min
            w = x_max - x_min
            # 获取图片尺寸，计算TextScale
            img = cv2.imread(OriginalImagePath)
            H, W = img.shape[:2]
            min_side = min(H, W)
            # 判定横向还是竖向
            text_scale = round(w / min_side if h >= w else h / min_side, 2) if min_side > 0 else 0
            scale_ok = True # 只要内容合格，尺寸就算
            print("TextScale:", text_scale)
            
            x, y = x_min, y_min
            # 判断位置
            pos_result = judge_position(OriginalImagePath, (x, y, w, h))
            position_mode = pos_result.get('PositionMode', 0)
            print("position_mode", position_mode)

            if position_mode > 0:
                position_ok = True
                status = "合格" # 最终状态
                final_status_code = 1
            else:
                position_ok = False
                status = "内容合格，位置错误"
        else:
            # 内容不合格
            status = "没有检测到标识"


        output = {
                "status": final_status_code,
                "result": status,
                "ExplicitLabel": [
                    ["LableContent", lable_content, content_ok],
                    ["PositionMode", position_mode, position_ok],
                    ["TextScale", text_scale, scale_ok]
                ]
            }
        # print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        # 捕获任何可能的异常，并以标准格式返回
        return json.dumps({
            "status": -2,
            "result": f"执行错误: {str(e)}",
            "ExplicitLabel": [
                ["LableContent", None, False],
                ["PositionMode", None, False],
                ["TextScale", None, False]
            ]
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
    result_json = DetectImageExplicitLabel(image_path)
    if result_json:
        print(result_json, flush=True)
    # process_image(image_path)
    
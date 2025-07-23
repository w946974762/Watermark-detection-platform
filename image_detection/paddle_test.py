import json
from paddleocr import PaddleOCR
import numpy as np

def paddle_test(ocr_engine, image_path):
    """
    使用传入的PaddleOCR引擎进行识别，并返回文本和包围盒。
    """
    # 使用ocr方法，它在内部调用predict并处理结果
    # 对于单张图片，结果是一个list，包含一个子list，子list里是每一行识别结果
    # e.g., [[[box, (text, score)], [box, (text, score)], ...]]
    result = ocr_engine.ocr(image_path, cls=True)

    # 检查是否没有识别到任何内容
    if result is None or not result or not result[0]:
        print("未识别到任何文本。")
        return [], []

    # 提取识别结果
    lines = result[0]
    
    # 提取所有识别出的文本
    rec_texts = [line[1][0] for line in lines]

    # 提取所有包围盒，并转换为 [x_min, y_min, x_max, y_max] 格式
    rec_boxes = []
    for line in lines:
        # box的格式是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        box = np.array(line[0]).astype(np.int32)
        x_min = np.min(box[:, 0])
        y_min = np.min(box[:, 1])
        x_max = np.max(box[:, 0])
        y_max = np.max(box[:, 1])
        rec_boxes.append([int(x_min), int(y_min), int(x_max), int(y_max)])
            
    return rec_texts, rec_boxes
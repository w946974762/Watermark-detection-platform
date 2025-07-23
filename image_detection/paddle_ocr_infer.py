import sys
from paddleocr import PaddleOCR
import cv2
import numpy as np
import re

def enhance_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    return enhanced

def sliding_window(image, step=30, window_size=(100, 40)):
    H, W = image.shape[:2]
    for y in range(0, max(1, H - window_size[1] + 1), step):
        for x in range(0, max(1, W - window_size[0] + 1), step):
            yield (x, y, image[y:y + window_size[1], x:x + window_size[0]])

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python paddle_ocr_infer.py 图片路径')
        sys.exit(1)
    image_path = sys.argv[1]
    ocr = PaddleOCR(use_angle_cls=False, lang='ch')
    img = cv2.imread(image_path)
    # 1. 先用PaddleOCR文本检测获得所有文本框区域
    det_result = ocr.ocr(image_path, det=True, rec=False)
    candidate_crops = []
    for line in det_result:
        for box in line:
            pts = box[0]
            x_min = int(min([p[0] for p in pts]))
            x_max = int(max([p[0] for p in pts]))
            y_min = int(min([p[1] for p in pts]))
            y_max = int(max([p[1] for p in pts]))
            # 加padding防止切割过紧
            pad = 5
            x_min = max(0, x_min - pad)
            y_min = max(0, y_min - pad)
            x_max = min(img.shape[1], x_max + pad)
            y_max = min(img.shape[0], y_max + pad)
            crop = img[y_min:y_max, x_min:x_max]
            candidate_crops.append(crop)
    # 2. 对每个候选区域做增强和分块识别
    all_results = []
    for crop in candidate_crops:
        # 原始区域
        res1 = ocr.ocr(crop)
        # 增强区域
        enhanced = enhance_image(crop)
        enhanced_path = 'enhanced_tmp.png'
        cv2.imwrite(enhanced_path, enhanced)
        res2 = ocr.ocr(enhanced_path)
        # 分块滑窗
        block_results = []
        window_size = (min(100, crop.shape[1]), min(40, crop.shape[0]))
        step = 20
        for (x, y, block) in sliding_window(crop, step=step, window_size=window_size):
            block_path = 'block_tmp.png'
            cv2.imwrite(block_path, block)
            block_results += ocr.ocr(block_path)
        all_results.extend(res1)
        all_results.extend(res2)
        all_results.extend(block_results)
    # 3. 输出所有中文内容
    print('识别结果:')
    for line in all_results:
        texts = line.get('rec_texts', [])
        scores = line.get('rec_scores', [])
        for text, score in zip(texts, scores):
            chinese_text = ''.join(re.findall(r'[\u4e00-\u9fff]+', text))
            if chinese_text:
                print(f'{chinese_text} (置信度: {score:.2f})')
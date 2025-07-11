import easyocr
import cv2
from typing import List, Tuple

def recognize_text(image_path: str, regions: List[Tuple[int, int, int, int]], lang_list=None) -> List[str]:
    """
    对每个区域进行文字识别，返回每个区域的识别文字。
    regions: [(x, y, w, h), ...]
    """
    if lang_list is None:
        lang_list = ['ch_sim', 'en']
    reader = easyocr.Reader(lang_list, gpu=False)
    image = cv2.imread(image_path)reader = easyocr.Reader(['ch_sim', 'en'], gpu=True)
    results = []
    for (x, y, w, h) in regions:
        crop = image[y:y+h, x:x+w]
        result = reader.readtext(crop)
        if result:
            # 取置信度最高的结果
            text = max(result, key=lambda x: x[2])[1]
        else:
            text = ''
        results.append(text)
    return results 
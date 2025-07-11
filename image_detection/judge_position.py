from typing import Tuple
import cv2

def judge_position(image_path: str, region: Tuple[int, int, int, int], edge_ratio: float = 0.05) -> str:
    """
    判断显式标识是否在图片边缘/角落，且高度不低于图片最短边5%。
    region: (x, y, w, h)
    """
    image = cv2.imread(image_path)
    H, W = image.shape[:2]
    x, y, w, h = region
    min_side = min(H, W)
    # 判断高度
    if h < min_side * edge_ratio:
        return "标识位置错误"
    # 判断是否在边缘或角落
    margin = int(min_side * edge_ratio)
    in_left = x <= margin
    in_right = x + w >= W - margin
    in_top = y <= margin
    in_bottom = y + h >= H - margin
    # 只要在任意一条边或角落即可
    if in_left or in_right or in_top or in_bottom:
        return "标识位置正确"
    return "标识位置错误" 
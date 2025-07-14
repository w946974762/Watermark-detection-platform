from typing import Tuple, Dict
import cv2

def judge_position(image_path: str, region: Tuple[int, int, int, int], edge_ratio: float = 0.05) -> Dict[str, int]:
    """
    判断显式标识是否在图片边缘/角落，并返回对应的位置模式。
    region: (x, y, w, h)
    返回值：
        {'PositionMode': mode}，其中 mode 是以下之一：
            1(右下), 2(左下), 3(右上), 4(左上),
            -1(下中), -2(上中), -3(左中), -4(右中)
    """
    image = cv2.imread(image_path)
    H, W = image.shape[:2]
    x, y, w, h = region
    min_side = min(H, W)
    
    # 判断高度是否满足最低要求
    if h < min_side * edge_ratio:
        return {"PositionMode": 0}  # 不符合最小高度要求

    margin = int(min_side * edge_ratio)

    in_left = x <= margin
    in_right = x + w >= W - margin
    in_top = y <= margin
    in_bottom = y + h >= H - margin

    # 四个角的判断优先级高于中间区域
    if in_left and in_top:
        return {"PositionMode": 4}
    elif in_right and in_top:
        return {"PositionMode": 3}
    elif in_left and in_bottom:
        return {"PositionMode": 2}
    elif in_right and in_bottom:
        return {"PositionMode": 1}

    # 中间区域
    elif in_left:
        return {"PositionMode": -3}
    elif in_right:
        return {"PositionMode": -4}
    elif in_top:
        return {"PositionMode": -2}
    elif in_bottom:
        return {"PositionMode": -1}

    return {"PositionMode": 0}
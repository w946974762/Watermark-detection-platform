from typing import List, Tuple
import re

def normalize_ai(text: str) -> str:
    # 替换常见误识别（如41、4I、A1、Al、aI、N等为AI）
    # 替换常见误识别
    text = text.replace('Al', 'AI').replace('A1', 'AI').replace('41', 'AI').replace('4I', 'AI')
    text = re.sub(r'^4[1I]', 'AI', text, flags=re.IGNORECASE)
    text = re.sub(r'^A[1lI]', 'AI', text, flags=re.IGNORECASE)
    text = re.sub(r'^N', 'AI', text, flags=re.IGNORECASE)  # 直接归一化为AI
    text = text.replace('堡咸', '生成')  # 误识别容错
    text = text.replace('兀', '人工')  # 误识别容错
    text = text.replace('从', '人工')  # 误识别容错
    text = text.replace('船', '能')  # 误识别容错
    text = text.replace('INI', 'AI')  # 误识别容错
    text = re.sub(r'[^\w\u4e00-\u9fff]', '', text)  # 只保留字母、数字、中文
    text = text.replace(' ', '').upper()
    return text

def judge_content(texts: List[str]) -> Tuple[int, str, str, str]:
    """
    返回：
    - idx: 匹配到的原始内容索引
    - result: 原始内容（或拼接内容）
    - norm_result: 归一化内容
    - 状态字符串：'合法'/'检测到标识内容但位置错误'/'没有检测到标识'
    """
    valid_set = {"人工智能生成", "人工智能合成", "AI生成", "AI合成", "合成AI", "生成AI"}
    valid_set = {normalize_ai(x) for x in valid_set}
    # 1. 先判定单个内容
    if not texts:
        return None, None, None, "没有检测到标识" 
    for idx, text in enumerate(texts):
        if text in valid_set:
            return idx, text, text, "合格"
    # 2. 拼接所有非空内容后判定
    non_empty_texts = [t for t in texts if t.strip()]
    concat_text = ''.join(non_empty_texts)
    if concat_text in valid_set:
        return 0, concat_text, concat_text, "合格"
    # 3. 兜底
    return None, None, None, "检测到错误标识内容"
from typing import List
import re

def normalize_ai(text: str) -> str:
    """
    将常见的AI误识别（如Al、aI、A1等）替换为AI，并统一大写。
    """
    # 替换常见误识别
    text = re.sub(r'\bA[l1iI]\b', 'AI', text, flags=re.IGNORECASE)
    text = text.upper()
    return text

def judge_content(texts: List[str]) -> str:
    """
    判断识别结果中是否同时包含（“人工智能”或“AI”）和（“生成”或“合成”）的组合，顺序不限。
    返回：
    - 错误标识：未包含
    - 具体内容：包含
    """
    keywords1 = ["人工智能", "AI"]
    keywords2 = ["生成", "合成"]
    for text in texts:
        norm_text = normalize_ai(text)
        has_k1 = any(k1 in norm_text for k1 in [k.upper() for k in keywords1])
        has_k2 = any(k2 in norm_text for k2 in [k.upper() for k in keywords2])
        if has_k1 and has_k2:
            return text
    return "错误标识" 
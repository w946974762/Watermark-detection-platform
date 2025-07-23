from typing import List, Tuple
import re

def normalize_ai(text: str) -> str:
    # 替换常见误识别（如41、4I、A1、Al、aI、N等为AI）
    # 替换常见误识别
    text = text.replace('Al', 'AI').replace('A1', 'AI').replace('41', 'AI').replace('4I', 'AI')
    text = re.sub(r'^A[1lI]?', 'AI', text, flags=re.IGNORECASE) # 修正：A, A1, Al, AI 都可
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
    对识别出的文本列表进行内容和拼接判断。
    返回：
    - idx: 匹配到的原始内容在原始列表中的索引，如果拼接成功则为0。
    - result: 匹配到的原始内容（或拼接内容）。
    - norm_result: 归一化后的内容。
    - 状态字符串：'合格' 或 '没有检测到标识'。
    """
    if not texts:
        return None, None, None, "没有检测到标识"

    normalized_texts = [normalize_ai(t) for t in texts]
    valid_keywords = {"人工智能生成", "人工智能合成", "A生成", "A合成", "AI生成", "AI合成", "合成AI", "生成AI"}
    
    # 1. 检查单个归一化后的文本是否完全匹配
    for i, norm_text in enumerate(normalized_texts):
        # 增加对 "A生成" -> "AI生成" 的直接判断
        if "A生成" in norm_text:
            norm_text = norm_text.replace("A生成", "AI生成")
        if "A合成" in norm_text:
            norm_text = norm_text.replace("A合成", "AI合成")
            
        if norm_text in valid_keywords:
            return i, texts[i], norm_text, "合格"

    # 2. 尝试拼接所有文本进行判断
    concatenated_text = "".join(normalized_texts)
    if "A生成" in concatenated_text:
        concatenated_text = concatenated_text.replace("A生成", "AI生成")
    if "A合成" in concatenated_text:
        concatenated_text = concatenated_text.replace("A合成", "AI合成")

    if concatenated_text in valid_keywords:
        # 如果是拼接成功的，原始文本就是所有非空文本的拼接
        original_concatenated = "".join([t for t in texts if t and t.strip()])
        return 0, original_concatenated, concatenated_text, "合格"

    # 3. 如果都匹配不到
    # 返回第一个识别到的内容作为错误内容
    return 0, texts[0] if texts else "", normalized_texts[0] if normalized_texts else "", "没有检测到标识"
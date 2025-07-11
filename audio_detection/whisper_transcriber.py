import sys
import os
import torch
sys.path.append(os.path.abspath("/seal_flask/audio_detection/"))
import whisper
from typing import Optional, List, Tuple, Dict

# 选择模型大小（根据需求和硬件选择）
# 可选：tiny, base, small, medium, large
MODEL_SIZE = "medium"  # 中等大小，平衡速度和准确率


def transcribe_audio(audio_path: str, language: Optional[str] = None) -> Dict:
    """
    使用 Whisper 模型转录音频文件，返回详细的转录结果（包含时间戳）

    参数:
        audio_path: 输入音频文件路径
        language: 音频语言（如"zh"、"en"等，可选，模型会自动检测）

    返回:
        包含完整转录信息的字典，包括文本和分段时间戳
    """
    # 检查文件是否存在
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    # 加载模型
    # device = "cuda" if torch.cuda.is_available() else "cpu"
    device = "cpu"
    model = whisper.load_model(MODEL_SIZE, device=device)

    # 设置转录参数
    options = {
        "language": language,
        "task": "transcribe",
        "beam_size": 5,
        "best_of": 5,
        "temperature": 0.0,
        "word_timestamps": True  # 启用词级时间戳
    }

    # 执行转录
    result = model.transcribe(audio_path, **options)
    return result


def detect_ai_labels_with_timestamps(transcription_result: Dict) -> List[Tuple[str, float]]:
    """
    检测转录文本中是否包含指定的 AI 生成/合成标识，并返回匹配文本及其开始时间

    参数:
        transcription_result: transcribe_audio 返回的完整结果

    返回:
        列表，每个元素是一个元组(匹配的文本, 开始时间)
    """
    target_labels = ["人工智能生成", "人工智能合成", "AI生成", "AI合成"]
    matches = []

    # 遍历所有分段
    for segment in transcription_result["segments"]:
        segment_text = segment["text"]
        segment_start = segment["start"]

        # 检查当前分段是否包含任何目标关键词
        for label in target_labels:
            start_idx = 0
            while start_idx < len(segment_text):
                pos = segment_text.find(label, start_idx)
                if pos == -1:
                    break

                # 计算关键词在分段内的起始时间
                # 分段文本总时长
                segment_duration = segment["end"] - segment_start  
                # 关键词起始位置占分段文本的比例
                ratio = pos / len(segment_text)  
                # 关键词在音频中的起始时间
                label_start = segment_start + ratio * segment_duration  

                # 尝试用词级时间戳优化
                if "words" in segment:
                    # 找到包含关键词起始位置的单词
                    for word_info in segment["words"]:
                        word_start = word_info["start"]
                        word_end = word_info["end"]
                        # 关键词起始时间在当前单词时间范围内
                        if word_start <= label_start <= word_end:  
                            label_start = word_start
                            break

                matches.append((label, label_start))
                # 从当前匹配位置之后继续查找
                start_idx = pos + len(label)  

    return matches


def process_audio(audio_path: str, language: Optional[str] = None) -> List[Tuple[str, float]]:
    """
    处理音频文件：先转录为文本，再检测是否包含 AI 生成/合成标识，并返回匹配结果及其时间戳

    参数:
        audio_path: 输入音频文件路径
        language: 音频语言（可选，模型会自动检测）

    返回:
        列表，每个元素是一个元组(匹配的文本, 开始时间)
    """
    result = transcribe_audio(audio_path, language)
    return detect_ai_labels_with_timestamps(result)
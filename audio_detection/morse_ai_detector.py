import numpy as np
import librosa
import scipy.signal

# 固定摩斯码模板音频路径
MORSE_TEMPLATE_PATH = '/seal_flask/audio_detection/ai_result/morse0.wav'  # 请将此路径替换为你的摩斯码模板音频文件路径


def load_audio(file_path, sr=16000):
    audio, _ = librosa.load(file_path, sr=sr)
    audio = audio / np.max(np.abs(audio))
    return audio


def detect_ai_pattern(input_audio_path, threshold=0.7):
    """
    检测输入音频中所有摩斯码模板出现的位置。
    返回: matches = [(起始时间, 'AI:.- ..'), ...]
    """
    input_audio = load_audio(input_audio_path)
    morse_audio = load_audio(MORSE_TEMPLATE_PATH)
    sr = 16000  # 与load_audio一致

    # 模板匹配
    correlation = scipy.signal.correlate(input_audio, morse_audio, mode='valid')
    norm_morse = np.linalg.norm(morse_audio)
    window_norms = np.array([
        np.linalg.norm(input_audio[i:i+len(morse_audio)])
        for i in range(len(correlation))
    ])
    correlation = correlation / (norm_morse * window_norms + 1e-8)

    # 找到所有大于阈值的位置
    matches = []
    min_distance = int(0.5 * sr)  # 0.5秒内只算一次匹配，避免重复
    last_idx = -min_distance
    for idx, value in enumerate(correlation):
        if value > threshold and (idx - last_idx) > min_distance:
            start_time = idx / sr
            matches.append((start_time, 'AI:.- ..'))
            last_idx = idx
    return matches
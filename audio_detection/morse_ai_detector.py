import numpy as np
import librosa


def detect_ai_pattern(audio_path, min_duration=0.02, tolerance=1.0):
    """
    检测音频中的摩斯码"AI"(·-··)模式
    参数:
        audio_path: 音频文件路径
        min_duration: 最小音段持续时间(秒)，用于过滤噪声
        tolerance: 模式匹配的容差阈值
    返回:
        matches: 检测到的匹配列表，每个元素为(起始时间, 持续时间列表)
    """
    # 加载音频
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    # 预处理：预加重增强高频
    y = librosa.effects.preemphasis(y, coef=0.95)

    # 设置帧参数 (30ms帧长，50%重叠)
    frame_len = int(0.03 * sr)  # 30ms帧
    hop_len = frame_len // 2

    # 端点检测：计算短时能量
    energy = np.array([
        np.sum(np.abs(y[i:i + frame_len]) ** 2)
        for i in range(0, len(y) - frame_len, hop_len)
    ])

    # 动态计算能量阈值
    energy_db = 10 * np.log10(energy + 1e-10)
    noise_floor = np.percentile(energy_db, 30)
    speech_thresh = noise_floor + 6  # 高于噪声层6dB

    # 转换为线性标度阈值
    linear_thresh = 10 ** (speech_thresh / 10)
    voiced = energy > linear_thresh

    # 合并连续的有声段
    segments = []
    start_idx = None
    for i, v in enumerate(voiced):
        if v and start_idx is None:
            start_idx = i
        elif not v and start_idx is not None:
            # 计算时间(秒)
            start_time = start_idx * hop_len / sr
            end_time = (i - 1) * hop_len / sr
            duration = end_time - start_time

            # 过滤短于最小持续时间的段
            if duration >= min_duration:
                segments.append((start_time, end_time, duration))
            start_idx = None

    # 处理音频末尾的有声段
    if start_idx is not None:
        start_time = start_idx * hop_len / sr
        end_time = (len(voiced) - 1) * hop_len / sr
        duration = end_time - start_time
        if duration >= min_duration:
            segments.append((start_time, end_time, duration))

    # 如果没有检测到有声段，直接返回
    if not segments:
        return []

    # 计算单位时间(最短有效音段的持续时间)
    min_duration = min(dur for _, _, dur in segments)
    unit = max(min_duration, 0.02)  # 确保单位时间不小于20ms

    # 归一化持续时间
    norm_durations = [dur / unit for _, _, dur in segments]

    # 目标模式: 短(1)-长(3)-短(1)-短(1)
    target_pattern = np.array([1.0, 3.0, 1.0, 1.0])

    # 寻找所有匹配
    matches = []
    for i in range(len(norm_durations) - 3):
        # 提取当前窗口的4个音段
        current_segments = segments[i:i + 4]
        current_durations = norm_durations[i:i + 4]

        # 计算模式匹配误差
        error = np.sum(np.abs(np.array(current_durations) - target_pattern))

        # 检查是否匹配
        if error < tolerance:
            # 获取第一个音段的起始时间
            start_time = segments[i][0]
            # 存储匹配信息: 起始时间 + 实际持续时间序列
            matches.append((
                start_time,
                [dur for _, _, dur in current_segments]
            ))

    return matches
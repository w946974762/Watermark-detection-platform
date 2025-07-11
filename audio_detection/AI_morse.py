import numpy as np
import wave
import math


def generate_morse_audio(output_file="ai_morse.wav"):
    """
    生成包含 "AI" 摩斯码(.- ..)的音频文件
    参数:
        output_file: 输出音频文件名(默认: ai_morse.wav)
    """
    # 音频参数
    sample_rate = 44100  # 采样率(Hz)
    duration_dot = 0.1  # 点(.)的持续时间(秒)
    duration_dash = 3 * duration_dot  # 划(-)持续时间(3倍点)
    freq = 800  # 摩斯码音频频率(Hz)
    amplitude = 0.5  # 音量(0-1)

    # "AI" 的摩斯码: .- ..
    morse_pattern = [
        (1, duration_dot),  # . (点)
        (0, duration_dot),  # 字符内间隔
        (1, duration_dash),  # - (划)
        (0, duration_dot * 3),  # 字符间间隔
        (1, duration_dot),  # . (点)
        (0, duration_dot),  # 字符内间隔
        (1, duration_dot),  # . (点)
        (0, duration_dot * 7)  # 单词结束间隔
    ]

    # 生成音频数据
    audio_data = np.array([], dtype=np.float32)
    time_values = np.linspace(0, duration_dot, int(sample_rate * duration_dot), False)

    for signal_type, duration in morse_pattern:
        if signal_type == 1:  # 信号(正弦波)
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            signal = amplitude * np.sin(2 * np.pi * freq * t)
        else:  # 静音
            signal = np.zeros(int(sample_rate * duration))
        audio_data = np.concatenate((audio_data, signal))

    # 转换为16位PCM格式
    audio_data = np.int16(audio_data * 32767)

    # 保存为WAV文件
    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位(2字节)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())

    print(f"已生成摩斯码音频文件: {output_file}")


if __name__ == "__main__":
    # 生成音频文件
    generate_morse_audio()

    # 验证生成的文件
    try:
        import simpleaudio as sa

        print("正在播放生成的摩斯码音频...")
        wave_obj = sa.WaveObject.from_wave_file("ai_morse.wav")
        play_obj = wave_obj.play()
        play_obj.wait_done()
    except ImportError:
        print("如需播放音频，请安装 simpleaudio: pip install simpleaudio")

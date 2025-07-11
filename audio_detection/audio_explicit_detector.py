import json
from typing import Dict, List
from .whisper_transcriber import process_audio
from .morse_ai_detector import detect_ai_pattern


def DetectAudioExplicitLabel(OriginalAudioPath: str) -> str:
    """
    检测音频中已嵌入的听觉标识信息。

    参数：
        OriginalAudioPath (str): 音频文件路径。

    返回：
        str: JSON 字符串，格式如下：
        {
            "status": 1 | -1 | -2,
            "result": "检测说明",
            "ExplicitLabel": [
                ["LableMode", "语音标识"/"节奏标识", true/false],
                ["Positions", [0], true/false], // 提示音的开始时间，可以是多个位置
                ["LableContent", "AI生成", true/false],
            ]
        }
    """
    try:
        # ============= 1. 初始化结果结构 =============
        result_data: Dict[str, any] = {
            "status": 1,  # 1=成功, -1=文件错误, -2=其他错误
            "result": "检测完成",
            "ExplicitLabel": []
        }

        # ============= 2. 语音标识检测（Whisper 部分） =============
        speech_matches = process_audio(OriginalAudioPath)
        speech_label = {
            "LableMode": "语音标识",
            "Positions": [start_time for _, start_time in speech_matches] if speech_matches else [],
            "LableContent": any(speech_matches),  # 是否检测到内容
            "MatchedTexts": [text for text, _ in speech_matches] if speech_matches else []
        }
        result_data["ExplicitLabel"].append(speech_label)

        # ============= 3. 节奏标识检测（摩斯码部分） =============
        morse_matches = detect_ai_pattern(OriginalAudioPath)
        morse_label = {
            "LableMode": "节奏标识",
            "Positions": [start_time for start_time, _ in morse_matches] if morse_matches else [],
            "LableContent": any(morse_matches),  # 是否检测到内容
            "MatchedDurations": [durs for _, durs in morse_matches] if morse_matches else []
        }
        result_data["ExplicitLabel"].append(morse_label)

        # ============= 4. 状态与结果说明 =============
        if not speech_matches and not morse_matches:
            result_data["status"] = 1
            result_data["result"] = "未检测到任何显式标识"
        else:
            result_data["status"] = 1
            result_data["result"] = "检测到显式标识"

    except FileNotFoundError as e:
        result_data = {
            "status": -1,
            "result": f"文件错误: {str(e)}",
            "ExplicitLabel": []
        }
    except Exception as e:
        result_data = {
            "status": -2,
            "result": f"检测异常: {str(e)}",
            "ExplicitLabel": []
        }

    # 转为 JSON 字符串返回
    return json.dumps(result_data, ensure_ascii=False, indent=2)


# 测试示例
if __name__ == "__main__":
    test_audio_path = "/root/Explicit_Audio_Detection/ai_result/real_voice1_scale_volume.mp3"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/real_voice2_volume0.5_speed1.mp3"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/real_voice3_volume0.5_speed1.mp3"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/real_voice4_volume0.4_speed0.mp3"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/morse0.wav"  # 替换为实际路径
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/morse1.wav"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/morse2.wav"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/morse3.wav"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/new_real_morse_volume0.4_speed0.mp3"
    # test_audio_path = "/root/Explicit_Audio_Detection/ai_result/real_morse.wav"

    output = DetectAudioExplicitLabel(test_audio_path)
    print(output)

import json
import os
from pydub import AudioSegment


def EmbedAudioExplicitLabel(OriginalAudioPath: str, ResultFilePath: str, ExplicitLabel: dict) -> str:
    """
    在音频中嵌入听觉标识（语音/节奏标识）。
    参数：
     OriginalAudioPath (str): 原始音频路径。
     ResultFilePath (str): 嵌入标识后的音频输出路径。
     ExplicitLabel (dict):
         {
         'LableAudioPath': 'url', # 标识音文件路径
         'Positions': [0],        # list，提示音嵌入的开始时间（秒），可以多个
         'Volume': 0,             # float, -1.0 ~ 1.0，0为原始音量
         'Speed': 0,              # float, 0.0~1.0，0=120字/分，1=160字/分
         }
    返回：
     str: JSON 字符串，格式如下：
     {
      "status": 1 | 0 | -1 | -2, // 1: 嵌入成功, 0: 未嵌入, -1: 嵌入失败, -2: 执行错误
      "result": "结果说明"
     }
    """
    try:
        label_audio_name = ExplicitLabel.get('LableAudioPath')
        print(label_audio_name)
        current_dir = os.path.dirname(__file__)
        # 提示音基础路径：/seal_flask/audio_explicit/ai_label/
        label_audio_dir = os.path.join(current_dir, 'ai_label')

        # 检查原始音频和标识音是否存在
        if not os.path.exists(OriginalAudioPath):
            return json.dumps({"status": -1, "result": f"原始音频文件不存在: {OriginalAudioPath}"})
        if not os.path.exists(os.path.join(label_audio_dir, f"{ExplicitLabel['LableAudioPath']}.wav")):
            return json.dumps({"status": -1, "result": f"标识音文件不存在: {ExplicitLabel['LableAudioPath']}"}, ensure_ascii=False)

        # 加载音频
        audio = AudioSegment.from_file(OriginalAudioPath)
        label = AudioSegment.from_file(os.path.join(label_audio_dir, f"{ExplicitLabel['LableAudioPath']}.wav"))

        # 音量调整
        if 'Volume' in ExplicitLabel:
            # pydub的dB增益，0为原始音量，负数为降低，正数为提高
            # 这里假设-1.0~1.0线性映射到-20dB~+20dB
            gain_db = float(ExplicitLabel['Volume']) * 20
            label = label + gain_db

        # 语速调整
        if 'Speed' in ExplicitLabel:
            # 0.0~1.0 映射到 120~160字/分，等价于 1.0~1.33倍速
            speed = 1.0 + 0.33 * float(ExplicitLabel['Speed'])
            label = label._spawn(label.raw_data, overrides={
                "frame_rate": int(label.frame_rate * speed)
            }).set_frame_rate(label.frame_rate)

        # 嵌入标识音
        positions = ExplicitLabel.get('Positions', [0])
        positions = sorted(set([max(0, int(float(p))) for p in positions]))
        if not positions:
            return json.dumps({"status": 0, "result": "未指定嵌入位置"},ensure_ascii=False)
        if positions[-1]*1000 > len(audio):
            return json.dumps({"status": -1, "result": "嵌入位置超出原音频时长"},ensure_ascii=False)

        output = audio
        # 逆序插入，避免位置偏移
        for pos in sorted(positions, reverse=True):
            ms = int(pos * 1000)
            before = output[:ms]
            after = output[ms:]
            output = before + label + after

        output.export(ResultFilePath, format="mp3")
        return json.dumps({"status": 1, "result": f"嵌入成功，输出文件: {ResultFilePath}"},ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": -2, "result": f"执行错误: {str(e)}"}, ensure_ascii=False)


result = EmbedAudioExplicitLabel(
    OriginalAudioPath="ai/real_original.wav",
    ResultFilePath="ai_result/real_ai.mp3",
    ExplicitLabel={
        "LableAudioPath": "ai_label/voice1.wav",
        "Positions": [0],  # 在0秒和10秒插入
        "Volume": -1,
        "Speed": 0.8
    }
)
print(result)
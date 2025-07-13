import morse_talk as mtalk
from pydub import AudioSegment, generators
from pydub.utils import make_chunks

def extract_morse_from_audio(audio_path, unit_ms=120, threshold_db=-30):
    """从音频中提取摩斯码，并返回摩斯码字符串和时间事件列表"""
    audio = AudioSegment.from_file(audio_path)
    chunk_ms = 10
    chunks = make_chunks(audio, chunk_ms)
    state = "silence"
    current_len = 0
    results = []  # 存储 (状态, 持续时间, 起始时间)

    for i, chunk in enumerate(chunks):
        start_time = i * chunk_ms
        if chunk.dBFS > threshold_db:
            if state == "silence" and current_len > 0:
                results.append(("silence", current_len, start_time - current_len))
                current_len = 0
            state = "sound"
            current_len += chunk_ms
        else:
            if state == "sound" and current_len > 0:
                results.append(("sound", current_len, start_time - current_len))
                current_len = 0
            state = "silence"
            current_len += chunk_ms
    
    if current_len > 0:
        results.append((state, current_len, len(chunks) * chunk_ms - current_len))

    # 解析摩斯码
    morse = ""
    for t, l, _ in results:
        if t == "sound":
            if l < unit_ms * 1.5:
                morse += "."
            else:
                morse += "-"
        else:
            if l >= unit_ms * 7:
                morse += " / "
            elif l >= unit_ms * 3:
                morse += " "
    
    return morse, results


def detect_ai_pattern(audio_path, unit_ms=120, threshold_db=-30):
    """检测音频中AI摩斯码模式，并返回匹配的起始时间和摩斯码内容"""
    morse_code, time_events = extract_morse_from_audio(audio_path, unit_ms, threshold_db)
    ai_morse = mtalk.encode("AI")
    
    # 统一分隔符格式
    morse_code_std = morse_code.replace('/', '   ')
    morse_code_std = ' '.join(morse_code_std.strip().split())
    ai_morse_std = ' '.join(ai_morse.strip().split())
    
    print(f"标准化后摩斯码：{repr(morse_code_std)}")
    # print(f"标准化后AI摩斯码：{repr(ai_morse_std)}")
    
    # 如果没有匹配，直接返回空列表
    if ai_morse_std not in morse_code_std:
        print(f"标准化后AI摩斯码：{repr(ai_morse_std)}")
        return []
    
    # 查找所有匹配的AI摩斯码模式
    matches = []
    start_pos = 0
    
    while True:
        # 查找下一个匹配位置
        match_pos = morse_code_std.find(ai_morse_std, start_pos)
        print(f"match_pos：{match_pos}")
        if match_pos == -1:
            break
        
        # 计算匹配的起始时间
        # 需要找到匹配位置对应的声音事件
        target_morse = morse_code_std[:match_pos]
        
        # 重新构建摩斯码字符串，找到对应的声音事件
        current_morse = ""
        time_offset = None
        
        for event_type, duration, start_time in time_events:
            if event_type == "sound":
                # 根据持续时间判断是点还是划
                if duration < unit_ms * 1.5:
                    current_morse += "."
                else:
                    current_morse += "-"
            elif event_type == "silence":
                # 根据静音持续时间添加分隔符
                if duration >= unit_ms * 7:
                    current_morse += " / "
                elif duration >= unit_ms * 3:
                    current_morse += " "
            
            # 标准化当前摩斯码字符串进行比较
            current_std = ' '.join(current_morse.strip().split())
            
            # 检查是否已经到达或超过目标位置
            if current_std == target_morse or len(current_std) >= len(target_morse):
                time_offset = start_time
                break
        
        # 如果找到了匹配，添加到结果列表
        if time_offset is not None:
            matches.append((time_offset, "AI:.- .."))
        
        # 继续查找下一个匹配
        start_pos = match_pos + 1
    
    return matches 
import os
import json
import struct
import shutil
from typing import Optional, List, Tuple

# 导入mutagen 库，用于处理除WAV外的所有音频格式元数据
from mutagen.mp3 import MP3, HeaderNotFoundError
from mutagen.id3 import TXXX, ID3
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC
from mutagen.mp4 import MP4, MP4FreeForm

# --- 常量定义 ---
# 遵循《网络安全标准实践指南》的规定，用于在不同格式中唯一标识AIGC数据

# MP3格式：使用ID3v2标签中的TXXX帧，其“描述”字段固定为'AIGC'
MP3_AIGC_DESC = 'AIGC'
# OGG和FLAC格式：使用Vorbis Comment（一种键值对系统），其“键”固定为'AIGC'
VORBIS_AIGC_KEY = 'AIGC'
# M4A/MP4格式：使用MP4原子结构中的自定义“自由格式”原子，其名称为'AIGC'
# '----:com.apple.iTunes:' 是 mutagen 用来表示自定义原子的命名空间约定
M4A_AIGC_KEY = '----:com.apple.iTunes:AIGC'
# WAV格式：使用自定义的RIFF块，其块ID固定为'AIGC'
WAV_AIGC_CHUNK_ID = b'AIGC'


# --- WAV文件处理核心函数 ---

def _embed_wav_label(filepath: str, label: str) -> None:
    """
    【内部函数】为WAV文件嵌入AIGC元数据块。

    本函数采用“精确解析-安全重组”模式，以确保生成的WAV文件结构100%合规，
    能够被所有标准播放器和编辑器正确识别。

    工作流程:
    1. 精确解析: 将WAV文件按块(chunk)分解，分离出每个块的ID和其实际数据（不含填充）。
    2. 验证: 确保强制性的 'fmt ' 块存在，否则文件无效。
    3. 修改: 从块列表中移除任何已存在的旧 'AIGC' 块，以支持重复嵌入。
    4. 插入: 将新的 'AIGC' 块精确地插入到 'fmt ' 块之后，符合WAV规范。
    5. 安全重组: 按照标准顺序和对齐规则，将所有块重新写入文件，并更新文件头部的总大小。

    Args:
        filepath (str): 目标WAV文件路径。
        label (str): 要嵌入的JSON格式字符串。
    """
    try:
        with open(filepath, 'rb') as f:
            buffer = f.read()
    except FileNotFoundError:
        # 如果文件不存在，直接抛出异常，由上层函数处理
        raise

    # 步骤 1: 精确解析
    # 验证文件是否以 'RIFF' 开始，并包含 'WAVE' 标识
    if buffer[0:4] != b'RIFF' or buffer[8:12] != b'WAVE':
        raise ValueError("文件不是一个有效的WAV格式文件。")

    chunks: List[Tuple[bytes, bytes]] = []  # 用于存储 (块ID, 块的有效数据)
    offset = 12  # 从 'WAVE' 标识后开始解析
    while offset < len(buffer):
        chunk_id = buffer[offset:offset + 4]
        if len(chunk_id) < 4: break  # 文件末尾，不足以构成一个块ID

        chunk_size_bytes = buffer[offset + 4:offset + 8]
        if len(chunk_size_bytes) < 4: break  # 文件末尾，不足以构成一个块大小

        # 读取块头部记录的原始数据大小
        chunk_size = struct.unpack('<I', chunk_size_bytes)[0]

        # 读取未填充的有效载荷(payload)
        payload = buffer[offset + 8: offset + 8 + chunk_size]
        chunks.append((chunk_id, payload))

        # 计算偏移量，移动到下一个块的起始位置，正确处理奇数长度块的填充字节
        offset += 8 + chunk_size + (chunk_size % 2)

    # 步骤 2: 验证 'fmt ' 块是否存在
    if not any(cid == b'fmt ' for cid, payload in chunks):
        raise ValueError("WAV文件已损坏：未找到必需的 'fmt ' 块。")

    # 步骤 3: 修改块列表，移除任何已存在的旧 'AIGC' 块
    chunks = [(cid, payload) for cid, payload in chunks if cid != WAV_AIGC_CHUNK_ID]

    # 步骤 4: 创建并准备插入新的 'AIGC' 块
    new_payload = label.encode('utf-8')
    new_aigc_chunk = (WAV_AIGC_CHUNK_ID, new_payload)

    # 找到 'fmt ' 块的索引，以便在其后插入
    fmt_index = -1
    for i, (cid, payload) in enumerate(chunks):
        if cid == b'fmt ':
            fmt_index = i
            break

    # 将新块插入到 'fmt ' 块的后面一个位置
    chunks.insert(fmt_index + 1, new_aigc_chunk)

    # 步骤 5: 安全重组文件内容
    wave_content = bytearray()
    for cid, payload in chunks:
        wave_content += cid  # 写入块ID
        wave_content += struct.pack('<I', len(payload))  # 写入块的原始数据大小
        wave_content += payload  # 写入块的有效数据
        if len(payload) % 2 != 0:
            wave_content += b'\x00'  # 如果数据长度为奇数，添加一个填充字节

    # 步骤 6: 构建最终文件并更新RIFF头
    final_buffer = bytearray(b'RIFF')
    # 计算新的文件总大小 = 'WAVE'标识(4字节) + 所有块的总内容长度
    final_buffer += struct.pack('<I', 4 + len(wave_content))
    final_buffer += b'WAVE'
    final_buffer += wave_content

    # 将重组后的内容完整写回文件
    with open(filepath, 'wb') as f:
        f.write(final_buffer)


def _detect_wav_label(filepath: str) -> Optional[str]:
    """
    【内部函数】从WAV文件中检测并读取'AIGC'块的内容。

    工作流程:
    1. 逐块扫描文件。
    2. 找到块ID为 'AIGC' 的块。
    3. 读取其数据内容，并移除末尾可能存在的填充字节。
    4. 将清理后的数据解码为UTF-8字符串并返回。

    Args:
        filepath (str): 待检测的WAV文件路径。

    Returns:
        Optional[str]: 如果找到，返回JSON字符串；否则返回None。
    """
    try:
        with open(filepath, 'rb') as f:
            if f.read(4) != b'RIFF': return None
            f.seek(8)
            if f.read(4) != b'WAVE': return None

            while True:
                chunk_id_bytes = f.read(4)
                if not chunk_id_bytes: break

                chunk_size_bytes = f.read(4)
                if not chunk_size_bytes: break

                chunk_size = struct.unpack('<I', chunk_size_bytes)[0]

                if chunk_id_bytes == WAV_AIGC_CHUNK_ID:
                    data = f.read(chunk_size)
                    # 关键：解码前移除末尾所有填充的空字节，确保JSON有效性
                    return data.rstrip(b'\x00').decode('utf-8')

                # 如果不是目标块，则跳到下一个块的起始位置
                f.seek(chunk_size + (chunk_size % 2), os.SEEK_CUR)
    except (FileNotFoundError, struct.error, IndexError, HeaderNotFoundError):
        return None
    return None


# --- 公共接口函数 ---

def EmbedAudioImplicitLabel(OriginalAudioPath: str, ImplicitLabel: str, ResultFilePath: str) -> str:
    """
    说明：
        将隐式标识信息嵌入至音频的元数据中。支持WAV, MP3, OGG, FLAC, M4A等格式。
        此函数符合接口文档要求，返回特定格式的JSON字符串。

    参数：
        OriginalAudioPath (str): 原始音频文件路径。
        ImplicitLabel (str): 隐式标识信息，JSON 格式的字符串。
        ResultFilePath (str): 嵌入标识后音频的输出路径。

    返回：
        str: JSON 字符串，报告操作结果。格式为：
        {
            "status": 1 | -1 | -2,  // 1: 嵌入成功, -1: 嵌入失败, -2: 执行错误
            "result": "结果说明"
        }
    """
    # 检查原始文件是否存在
    if not os.path.exists(OriginalAudioPath):
        return json.dumps({"status": -1, "result": f"嵌入失败：原始文件未找到于 {OriginalAudioPath}"}, ensure_ascii=False)

    try:
        # 为保证操作的原子性和原始文件的安全，总是先复制文件再进行修改
        shutil.copy2(OriginalAudioPath, ResultFilePath)
    except Exception as e:
        return json.dumps({"status": -1, "result": f"嵌入失败：复制文件时出错: {e}"}, ensure_ascii=False)

    # 获取文件扩展名以判断格式
    ext = os.path.splitext(ResultFilePath)[1].lower()

    try:
        # 根据文件格式，调用相应的处理逻辑
        if ext == '.wav':
            _embed_wav_label(ResultFilePath, ImplicitLabel)

        elif ext == '.mp3':
            audio = MP3(ResultFilePath, ID3=ID3)
            if audio.tags is None: audio.add_tags()  # 如果没有标签，则创建一个
            audio.tags.delall(f'TXXX:{MP3_AIGC_DESC}')  # 移除旧的，防止重复
            audio.tags.add(TXXX(encoding=3, desc=MP3_AIGC_DESC, text=ImplicitLabel))
            audio.save()

        elif ext in ['.ogg', '.oga', '.flac']:
            # OGG和FLAC都使用Vorbis Comments，mutagen提供了统一的字典式接口
            audio = FLAC(ResultFilePath) if ext == '.flac' else OggVorbis(ResultFilePath)
            audio[VORBIS_AIGC_KEY] = ImplicitLabel
            audio.save()

        elif ext in ['.m4a', '.mp4']:
            audio = MP4(ResultFilePath)
            # 使用MP4FreeForm来存储自定义数据
            audio[M4A_AIGC_KEY] = MP4FreeForm(ImplicitLabel.encode('utf-8'))
            audio.save()

        else:
            # 如果文件格式不支持
            return json.dumps({"status": -1, "result": f"嵌入失败：不支持的文件格式 {ext}"}, ensure_ascii=False)

        # 所有操作成功
        return json.dumps({"status": 1, "result": "嵌入成功"}, ensure_ascii=False)

    except Exception as e:
        # 捕获所有可能的异常，如文件损坏、库错误等
        # 如果出错，删除可能已损坏的目标文件
        if os.path.exists(ResultFilePath):
            try:
                os.remove(ResultFilePath)
            except OSError:
                pass
        return json.dumps({"status": -2, "result": f"执行错误: {e}"}, ensure_ascii=False)


def DetectAudioImplicitLabel(OriginalAudioPath: str) -> str:
    """
    说明：
        检测音频文件元数据中嵌入的隐式标识信息。
        此函数符合接口文档要求，返回特定格式的JSON字符串。

    参数：
        OriginalAudioPath (str): 待检测的音频文件路径。

    返回：
        str: JSON 字符串，报告检测结果。格式为：
        {
            "status": 1 | -1 | -2,
            "result": "结果说明",
            "ImplicitLabel": "检测到的JSON字符串" | null
        }
    """
    if not os.path.exists(OriginalAudioPath):
        return json.dumps({"status": -2, "result": f"执行错误：文件未找到于 {OriginalAudioPath}", "ImplicitLabel": None}, ensure_ascii=False)

    ext = os.path.splitext(OriginalAudioPath)[1].lower()
    label = None

    try:
        # 根据文件格式，调用相应的检测逻辑
        if ext == '.wav':
            label = _detect_wav_label(OriginalAudioPath)

        elif ext == '.mp3':
            audio = MP3(OriginalAudioPath)
            if audio.tags:
                txxx_frames = audio.tags.getall('TXXX')
                for frame in txxx_frames:
                    if frame.desc == MP3_AIGC_DESC:
                        label = frame.text[0]
                        break

        elif ext in ['.ogg', '.oga', '.flac']:
            audio = FLAC(OriginalAudioPath) if ext == '.flac' else OggVorbis(OriginalAudioPath)
            if VORBIS_AIGC_KEY in audio:
                label = audio[VORBIS_AIGC_KEY][0]

        elif ext in ['.m4a', '.mp4']:
            audio = MP4(OriginalAudioPath)
            if M4A_AIGC_KEY in audio:
                # mutagen将自由格式原子数据存储为字节列表
                label = audio[M4A_AIGC_KEY][0].decode('utf-8')

        else:
            return json.dumps({"status": -2, "result": f"执行错误：不支持的文件格式 {ext}", "ImplicitLabel": None}, ensure_ascii=False)

        # 根据是否找到标签，返回不同的结果
        if label:
            return json.dumps({"status": 1, "result": "检测成功", "ImplicitLabel": label}, ensure_ascii=False)
        else:
            return json.dumps({"status": -1, "result": "未检测到隐式标识", "ImplicitLabel": None}, ensure_ascii=False)

    except Exception as e:
        # 捕获所有可能的异常
        return json.dumps({"status": -2, "result": f"执行错误: {e}", "ImplicitLabel": None}, ensure_ascii=False)


# --- 示例和测试代码 ---

if __name__ == '__main__':
    print("--- 音频元数据隐式标识工具测试 ---")

    test_dir = "audio_test_files"
    if not os.path.exists(test_dir): os.makedirs(test_dir)

    # 1. 准备输入数据
    implicit_label_str = json.dumps({
        "Label": "1", "ContentProducer": "2",
        "ProduceID": "uuid-a1b2c3d4-e5f6-7890-1234-567890abcdef", "ReservedCode1": "4",
        "ContentPropagator": "5", "PropagateID": "content-id-xyz-987", "ReservedCode2": "7"
    })


    # 2. 创建一个虚拟WAV文件用于测试
    def create_dummy_wav(filepath):
        if os.path.exists(filepath): return
        sample_rate = 44100;
        data = b'\x00\x00' * (sample_rate)  # 1秒静音
        with open(filepath, 'wb') as f:
            # RIFF Header
            f.write(b'RIFF');
            f.write(struct.pack('<I', 36 + len(data)));
            f.write(b'WAVE')
            # Format Chunk ('fmt ')
            f.write(b'fmt ');
            f.write(struct.pack('<I', 16));
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 1));
            f.write(struct.pack('<I', sample_rate))
            f.write(struct.pack('<I', sample_rate * 2));
            f.write(struct.pack('<H', 2))
            f.write(struct.pack('<H', 16))
            # Data Chunk ('data')
            f.write(b'data');
            f.write(struct.pack('<I', len(data)));
            f.write(data)
        print(f"创建了虚拟WAV文件: {filepath}")


    dummy_wav_path = os.path.join(test_dir, "dummy.wav")
    create_dummy_wav(dummy_wav_path)

    print("\n注意：对于 MP3, OGG, FLAC, M4A, 请手动在 "
          f"'{test_dir}' 文件夹中放置样本文件以进行完整测试。")

    # 3. 查找所有原始（未被标记过）的测试文件
    supported_files = [
        f for f in os.listdir(test_dir)
        if not f.startswith('labeled_') and os.path.splitext(f)[1].lower() in ['.wav', '.mp3', '.ogg', '.flac', '.m4a',
                                                                               '.mp4', '.oga']
    ]

    if not supported_files:
        print("\n未在测试目录中找到支持的音频文件，测试结束。")

    # 4. 遍历并执行测试
    for filename in supported_files:
        original_path = os.path.join(test_dir, filename)
        result_path = os.path.join(test_dir, f"labeled_{filename}")

        print(f"\n{'=' * 15} 测试文件: {filename} {'=' * 15}")

        # --- 嵌入测试 ---
        print(f"[*] 正在嵌入标识...")
        embed_result_str = EmbedAudioImplicitLabel(original_path, implicit_label_str, result_path)
        embed_result = json.loads(embed_result_str)
        print(f"    -> 嵌入API返回: {embed_result_str}")
        if embed_result.get('status') != 1: continue

        # --- 检测测试 ---
        print(f"[*] 正在检测标识...")
        detect_result_str = DetectAudioImplicitLabel(result_path)
        detect_result = json.loads(detect_result_str)
        print(f"    -> 检测API返回: {detect_result_str}")

        # --- 验证结果 ---
        if detect_result.get('status') == 1:
            retrieved_label_str = detect_result['ImplicitLabel']
            if retrieved_label_str == implicit_label_str:
                print("    -> \033[92m[验证成功]\033[0m 检测到的数据与原始嵌入数据一致！")
            else:
                print("    -> \033[91m[验证失败]\033[0m 检测到的数据与原始数据不匹配！")
        else:
            print("    -> \033[91m[验证失败]\033[0m 未能从已标记的文件中检测到数据。")
# 音频显式标识检测系统

## 项目概述
本系统基于 OpenAI Whisper 模型，实现对音频文件中 "AI生成" 相关语音标识和摩斯码节奏标识的自动检测。系统支持两种检测方式：
- **语音标识**：通过关键词匹配识别音频中的语音提示（如"AI生成"）
- **节奏标识**：通过音频能量分析识别摩斯码节奏（·-·· 对应 "AI"）

## 安装指南

### 环境准备
bash
# 创建虚拟环境（指定Python版本）
conda create -n audio-detect python=3.11
conda activate audio-detect

# 安装系统依赖（Linux/macOS）
sudo apt install ffmpeg  # Ubuntu/Debian
brew install ffmpeg      # macOS

# 安装Python依赖
pip install -r requirements.txt


### 依赖说明
系统核心依赖包括：
- `openai-whisper`：语音识别模型
- `torch`：深度学习框架
- `librosa`：音频信号处理
- `numpy/scipy`：科学计算基础库

完整依赖列表见 `requirements.txt`

## 使用说明

### 目录结构
```
Explicit_Audio_Detection/
├── ai/                        # 原始音频
├── ai-lable/                  # 显式标签音频
├── ai-result/                 # 合成音频输出目录
├── whisper/                   # 音频转文字模型
├── whisper_transcriber.py     # 语音识别模块
├── morse_ai_detector.py       # 摩斯码检测模块
├── audio_explicit_detector.py # 主程序
└── requirements.txt           # 依赖清单
```

### 运行检测
```bash
python audio_explicit_detector.py 
```

### 输出格式
系统返回JSON格式结果，包含检测状态和标识详情：
json
{
    "status": 0,
    "result": "检测完成",
    "ExplicitLabel": [
        {
            "LabelType": "语音标识",
            "StartTime": 10.2,
            "EndTime": 12.5,
            "Content": "AI生成"
        },
        {
            "LabelType": "节奏标识",
            "StartTime": 22.0,
            "EndTime": 25.0,
            "Content": "摩斯码:AI"
        }
    ]
}


## 核心模块说明

### 1. 语音识别模块 (`whisper_transcriber.py`)
基于Whisper模型实现音频转文字，提取关键词时间戳：
- `transcribe_audio(audio_path)`：加载音频并返回完整转录结果
- `detect_ai_labels_with_timestamps(transcript)`：检测关键词并返回时间戳
- `process_audio(audio_path)`：整合处理流程，返回匹配结果列表

### 2. 摩斯码检测模块 (`morse_ai_detector.py`)
检测音频中是否包含"AI"对应的摩斯码节奏：
- `detect_ai_pattern(audio_path)`：通过能量分析识别摩斯码模式，返回匹配的时间戳

### 3. 主程序 (`audio_explicit_detector.py`)
整合两个模块的功能，返回标准化JSON结果：
- `DetectAudioExplicitLabel(audio_path)`：接收音频路径，返回检测结果

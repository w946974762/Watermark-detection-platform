import os
import json
import cv2
import ffmpeg
import easyocr

def EmbedVideoExplicitLabel(OriginalVideoPath: str, ResultFilePath: str, ExplicitLabel: dict) -> str:
    try:
        # 从字典中提取参数，设置默认值
        label_content = ExplicitLabel.get('LableContent', 'AI生成')
        position_mode = ExplicitLabel.get('PositionMode', 1)
        text_direction = ExplicitLabel.get('TextDirection', 0)
        text_scale = ExplicitLabel.get('TextScale', 0.05)
        text_color = ExplicitLabel.get('TextColor', [0, 0, 0])
        font_name = ExplicitLabel.get('FontName', 1)
        opacity = ExplicitLabel.get('Opacity', 0.5)
        start_time = ExplicitLabel.get('StartTime', [0])
        duration = ExplicitLabel.get('Duration', 2)

        # 检查路径
        if not os.path.exists(OriginalVideoPath):
            return json.dumps({"status": 0, "result": "原始视频路径不存在"}, ensure_ascii=False)

        # 验证参数
        if text_scale < 0.05 or not (0 <= opacity <= 1.0):
            return json.dumps({"status": 0, "result": "参数错误：TextScale或Opacity值非法"}, ensure_ascii=False)

        if duration < 2:
            return json.dumps({"status": 0, "result": "参数错误：Duration不能小于2秒"}, ensure_ascii=False)

        # 字体映射（整数键到字体文件）
        font_map = {
            1: "fonts/msyh.ttc",  # 微软雅黑
            2: "fonts/simsun.ttc", # 宋体
            3: "fonts/simhei.ttf", # 黑体
            4: "fonts/arial.ttf",  # Arial
            5: "fonts/times.ttf"   # Times New Roman
        }
        font_file = font_map.get(font_name, None)
        if not font_file:
            return json.dumps({"status": 0, "result": "不支持的字体名称"}, ensure_ascii=False)

        # 构造颜色和透明度
        r, g, b = text_color
        a = int(255 * opacity)
        fontcolor = f"#{r:02x}{g:02x}{b:02x}{a:02x}"

        # 获取视频信息
        probe = ffmpeg.probe(OriginalVideoPath)
        video_stream = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
        if video_stream is None:
            return json.dumps({"status": -1, "result": "未找到视频流"})

        video_duration = float(probe["format"]["duration"])
        for st in start_time:
            if st < 0 or st + duration > video_duration:
                return json.dumps({"status": 0, "result": f"起始时间 {st} 不合法或超出视频时长"}, ensure_ascii=False)

        width = int(video_stream["width"])
        height = int(video_stream["height"])
        min_dim = min(width, height)
        fontsize = int(text_scale * min_dim)

        frame_rate = None
        if 'avg_frame_rate' in video_stream:
            fr = video_stream['avg_frame_rate']
            if '/' in fr:
                num, den = fr.split('/')
                frame_rate = float(num) / float(den)

        bitrate = video_stream.get('bit_rate', None)

        # 纵向文字
        if text_direction == 1:
            label_content = "\n".join(list(label_content))

        # 位置表达式
        position_expr = {
            1: f"x=w-tw-10:y=h-th-10",  # 右下
            2: f"x=10:y=h-th-10",       # 左下
            3: f"x=w-tw-10:y=10",       # 右上
            4: f"x=10:y=10",            # 左上
            -1: f"x=(w-tw)/2:y=h-th-10", # 下中
            -2: f"x=(w-tw)/2:y=10",      # 上中
            -3: f"x=10:y=(h-th)/2",      # 左中
            -4: f"x=w-tw-10:y=(h-th)/2"  # 右中
        }.get(position_mode, "x=10:y=10")

        drawtext_args_base = {
            "fontfile": font_file,
            "text": label_content,
            "fontsize": fontsize,
            "fontcolor": fontcolor,
            "x": position_expr.split(":")[0][2:],  # 去除 x=
            "y": position_expr.split(":")[1][2:],  # 去除 y=
            "alpha": "1"
        }

        video_input = ffmpeg.input(OriginalVideoPath)
        video_output = video_input

        for st in start_time:
            drawtext_args = drawtext_args_base.copy()
            drawtext_args["enable"] = f"between(t,{st},{st + duration})"
            video_output = video_output.drawtext(**drawtext_args)

        audio_output = video_input.audio

        output_args = {
            'c:v': 'mpeg4',
            'b:v': bitrate,
            'r': frame_rate,
            'c:a': 'copy'
        }
        output_args = {k: v for k, v in output_args.items() if v is not None}

        stream = ffmpeg.output(
            video_output,
            audio_output,
            ResultFilePath,
            **output_args
        )

        ffmpeg.run(stream, overwrite_output=True)

        return json.dumps({"status": 1, "result": "嵌入成功"}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": -2, "result": f"执行错误: {str(e)}"}, ensure_ascii=False)






def DetectVideoExplicitLabel(OriginalVideoPath: str) -> str:
    try:
        if not os.path.exists(OriginalVideoPath):
            return json.dumps({"status": -2, "result": "视频文件不存在", "ExplicitLabel": []}, ensure_ascii=False)

        # 获取视频总时长`
        try:
            probe = ffmpeg.probe(OriginalVideoPath)
            duration = float(probe["format"]["duration"])
        except Exception as e:
            return json.dumps({"status": -2, "result": f"获取视频信息失败: {str(e)}", "ExplicitLabel": []}, ensure_ascii=False)

        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        expected_keywords = ['AI合成', 'AI生成', '人工智能合成', '人工智能生成']

        detected_times = []
        detected_text = ""
        detected_pos = None
        detected_scale = None

        sample_interval = 0.2  # 每0.2秒抽一帧
        max_sample_sec = min(duration, 10)  # 最多采样前10秒

        t = 0.0
        while t < max_sample_sec:
            temp_frame_path = f"temp_frame_{int(t*100):04d}.jpg"
            try:
                (
                    ffmpeg
                    .input(OriginalVideoPath, ss=t)
                    .output(temp_frame_path, vframes=1)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error:
                t += sample_interval
                continue

            if not os.path.exists(temp_frame_path):
                t += sample_interval
                continue

            image = cv2.imread(temp_frame_path)
            os.remove(temp_frame_path)
            if image is None:
                t += sample_interval
                continue

            height, width = image.shape[:2]
            min_dim = min(height, width)

            results = reader.readtext(image)
            frame_text = ''
            x_min, y_min, x_max, y_max = width, height, 0, 0
            found = False

            for (bbox, text, conf) in results:
                if conf > 0.6 and text.strip():
                    if any(kw in text for kw in expected_keywords):
                        frame_text += text.strip()
                        for (x, y) in bbox:
                            x_min = min(x_min, x)
                            y_min = min(y_min, y)
                            x_max = max(x_max, x)
                            y_max = max(y_max, y)
                        found = True

            if found:
                detected_times.append(round(t, 1))  # 秒保留1位小数
                if not detected_text:
                    detected_text = frame_text
                    center_x = (x_min + x_max) / 2
                    center_y = (y_min + y_max) / 2
                    x_pct = center_x / width
                    y_pct = center_y / height
                    margin = 0.1

                    def near(val, target):
                        return abs(val - target) <= margin

                    pos_mode = 0
                    if near(x_pct, 0.9) and near(y_pct, 0.9):
                        pos_mode = 1
                    elif near(x_pct, 0.1) and near(y_pct, 0.9):
                        pos_mode = 2
                    elif near(x_pct, 0.9) and near(y_pct, 0.1):
                        pos_mode = 3
                    elif near(x_pct, 0.1) and near(y_pct, 0.1):
                        pos_mode = 4
                    elif near(y_pct, 0.9) and near(x_pct, 0.5):
                        pos_mode = -1
                    elif near(y_pct, 0.1) and near(x_pct, 0.5):
                        pos_mode = -2
                    elif near(x_pct, 0.1) and near(y_pct, 0.5):
                        pos_mode = -3
                    elif near(x_pct, 0.9) and near(y_pct, 0.5):
                        pos_mode = -4
                    detected_pos = pos_mode
                    detected_scale = (y_max - y_min) / min_dim

            t += sample_interval

        if not detected_times:
            return json.dumps({"status": -1, "result": "未检测到明显水印文字", "ExplicitLabel": []}, ensure_ascii=False)

        if detected_text is None:
            detected_text = ""
        if detected_pos is None:
            detected_pos = 0
        if detected_scale is None:
            detected_scale = 0.0

        content_valid = any(kw in detected_text for kw in expected_keywords)
        position_valid = detected_pos in [1, 2, 3, 4, -1, -2, -3, -4]
        scale_valid = detected_scale >= 0.05
        text_scale = float(round(detected_scale, 4))

        detected_times.sort()
        time_groups = []
        current_group = [detected_times[0]]

        for i in range(1, len(detected_times)):
            if abs(detected_times[i] - detected_times[i - 1]) <= 0.3:
                current_group.append(detected_times[i])
            else:
                time_groups.append(current_group)
                current_group = [detected_times[i]]
        time_groups.append(current_group)

        start_times = [round(g[0], 1) for g in time_groups]
        max_duration = max([round(g[-1] - g[0] + sample_interval, 1) for g in time_groups])

        result_json = {
            "status": 1,
            "result": "检测成功",
            "ExplicitLabel": [
                ["LableContent", str(detected_text), bool(content_valid)],
                ["PositionMode", int(detected_pos), bool(position_valid)],
                ["TextScale", float(text_scale), bool(scale_valid)],
                ["StartTime", [float(x) for x in start_times], True],
                ["Duration", float(max_duration), max_duration >= 2.0]
            ]
        }

        return json.dumps(result_json, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": -2, "result": f"执行错误: {str(e)}", "ExplicitLabel": []}, ensure_ascii=False)





# 调用示例
result = EmbedVideoExplicitLabel(
    OriginalVideoPath='1.mp4',
    ResultFilePath='output.mp4',
    ExplicitLabel={
        'LableContent': '人工智能合成',
        'PositionMode': 1,
        'TextDirection': 0,
        'TextScale': 0.05,
        'TextColor': [255, 255, 255],
        'FontName': 3,  # 对应黑体
        'Opacity': 0.7,
        'StartTime': [0],
        'Duration': 5
    }
)
print(result)


result = DetectVideoExplicitLabel('output.mp4')

print(result)
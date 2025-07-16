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





def normalize_label(text: str) -> str:
    """
    用于纠正 easyocr 中常见的识别错误
    """
    replacements = {
        'A1': 'AI',
        'Al': 'AI',
        '1I': 'AI',
        '4': 'A',
        '1': 'I',
        'l': 'I',
        ' ': '',
        '\n': ''
    }
    for wrong, right in replacements.items():
        text = text.replace(wrong, right)
    return text.strip()

def DetectVideoExplicitLabel(OriginalVideoPath: str) -> str:
    try:
        if not os.path.exists(OriginalVideoPath):
            return json.dumps({"status": -2, "result": "视频文件不存在", "ExplicitLabel": []}, ensure_ascii=False)

        try:
            probe = ffmpeg.probe(OriginalVideoPath)
            duration = float(probe["format"]["duration"])
        except Exception as e:
            return json.dumps({"status": -2, "result": f"获取视频信息失败: {str(e)}", "ExplicitLabel": []}, ensure_ascii=False)

        reader = easyocr.Reader(['ch_sim', 'en'], gpu=True)
        expected_keywords = ['AI生成', 'AI合成', '人工智能合成', '人工智能生成']

        sample_interval = 0.1
        max_sample_sec = min(duration, 15.0)
        detected_frames = []

        t = 0.0
        while t < max_sample_sec:
            temp_frame_path = f"temp_frame_{int(t * 100):04d}.jpg"
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
            x_min, y_min, x_max, y_max = width, height, 0, 0
            frame_text = ""

            for (bbox, text, conf) in results:
                text = normalize_label(text)
                if conf > 0.2 and text.strip() in expected_keywords:
                    frame_text = text.strip()
                    for (x, y) in bbox:
                        x_min = min(x_min, x)
                        y_min = min(y_min, y)
                        x_max = max(x_max, x)
                        y_max = max(y_max, y)
                    break

            if frame_text:
                cx = (x_min + x_max) / 2
                cy = (y_min + y_max) / 2
                x_pct = cx / width
                y_pct = cy / height
                margin = 0.1

                def near(v, t): return abs(v - t) <= margin
                pos_mode = 0
                if near(x_pct, 0.9) and near(y_pct, 0.9): pos_mode = 1
                elif near(x_pct, 0.1) and near(y_pct, 0.9): pos_mode = 2
                elif near(x_pct, 0.9) and near(y_pct, 0.1): pos_mode = 3
                elif near(x_pct, 0.1) and near(y_pct, 0.1): pos_mode = 4
                elif near(x_pct, 0.5) and near(y_pct, 0.9): pos_mode = -1
                elif near(x_pct, 0.5) and near(y_pct, 0.1): pos_mode = -2
                elif near(x_pct, 0.1) and near(y_pct, 0.5): pos_mode = -3
                elif near(x_pct, 0.9) and near(y_pct, 0.5): pos_mode = -4

                text_scale = (y_max - y_min) / min_dim
                detected_frames.append((round(t, 1), frame_text, pos_mode, text_scale))

            t += sample_interval

        if not detected_frames:
            return json.dumps({"status": -1, "result": "未检测到明显水印文字", "ExplicitLabel": []}, ensure_ascii=False)

        # 分组检测时间段（间隔≤0.6s视为连续）
        max_gap = 0.3
        grouped = []
        current = [detected_frames[0]]
        for i in range(1, len(detected_frames)):
            if detected_frames[i][0] - current[-1][0] <= max_gap:
                current.append(detected_frames[i])
            else:
                grouped.append(current)
                current = [detected_frames[i]]
        grouped.append(current)

        # 找到第一个持续时间 ≥2s 的段
        valid_group = None
        for group in grouped:
            duration_sec = round(group[-1][0] - group[0][0] + sample_interval, 1)
            if duration_sec >= 2.0:
                valid_group = group
                break

        if not valid_group:
            return json.dumps({"status": -1, "result": "未检测到持续时间 ≥2秒 的水印", "ExplicitLabel": []}, ensure_ascii=False)

        start_times = [float(valid_group[0][0])]
        duration = float(round(valid_group[-1][0] - valid_group[0][0] + sample_interval, 1))
        detected_text = str(valid_group[0][1])
        detected_pos = int(valid_group[0][2])
        text_scale = float(round(valid_group[0][3], 4))

        explicit_label = [
            ["LableContent", detected_text, detected_text in expected_keywords],
            ["PositionMode", detected_pos, detected_pos in [1, 2, 3, 4, -1, -2, -3, -4]],
            ["TextScale", text_scale, text_scale >= 0.05],
            ["StartTime", start_times, True],
            ["Duration", duration, duration >= 2.0]
        ]

        failed_fields = [item[0] for item in explicit_label if item[2] is not True]
        all_pass = len(failed_fields) == 0

        result_json = {
            "status": 1 if all_pass else -1,
            "result": "检测成功" if all_pass else f"检测失败：以下字段不符合要求：{', '.join(failed_fields)}",
            "ExplicitLabel": explicit_label
        }

        return json.dumps(result_json, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": -2,
            "result": f"执行错误: {str(e)}",
            "ExplicitLabel": []
        }, ensure_ascii=False)





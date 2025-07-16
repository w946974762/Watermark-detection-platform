import os
import json
import cv2
import ffmpeg
import easyocr

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

import os
import json
import cv2
import ffmpeg
import easyocr

def DetectVideoExplicitLabel(OriginalVideoPath: str) -> str:
    try:
        if not os.path.exists(OriginalVideoPath):
            return json.dumps({"status": -2, "result": "视频文件不存在", "ExplicitLabel": []}, ensure_ascii=False)

        # 获取视频总时长
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

import ffmpeg
import os
import json

def EmbedVideoExplicitLabel(
    OriginalVideoPath: str,
    ResultFilePath: str,
    LableContent: str,
    PositionMode: int,
    TextDirection: int,
    TextScale: float,
    TextColor: list,
    FontName: str,
    Opacity: float,
    StartTime: list,
    Duration: int
) -> str:
    try:
        # 检查路径
        if not os.path.exists(OriginalVideoPath):
            return json.dumps({"status": 0, "result": "原始视频路径不存在"}, ensure_ascii=False)

        # 验证参数
        if TextScale < 0.05 or not (0 <= Opacity <= 1.0):
            return json.dumps({"status": 0, "result": "参数错误：TextScale或Opacity值非法"}, ensure_ascii=False)

        if Duration < 2:
            return json.dumps({"status": 0, "result": "参数错误：Duration不能小于2秒"}, ensure_ascii=False)

        # 字体映射
        font_map = {
            "宋体": "fonts/simsun.ttc",
            "微软雅黑": "fonts/msyh.ttc",
            "黑体": "fonts/simhei.ttf",
            "Arial": "fonts/arial.ttf",
            "Times New Roman": "fonts/times.ttf"
        }
        font_file = font_map.get(FontName, None)
        if not font_file:
            return json.dumps({"status": 0, "result": "不支持的字体名称"}, ensure_ascii=False)

        # 构造颜色和透明度
        r, g, b = TextColor
        a = int(255 * Opacity)
        fontcolor = f"#{r:02x}{g:02x}{b:02x}{a:02x}"

        # 获取视频信息
        probe = ffmpeg.probe(OriginalVideoPath)
        video_stream = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
        if video_stream is None:
            return json.dumps({"status": -1, "result": "未找到视频流"})

        duration = float(probe["format"]["duration"])
        for st in StartTime:
            if st < 0 or st + Duration > duration:
                return json.dumps({"status": 0, "result": f"起始时间 {st} 不合法或超出视频时长"}, ensure_ascii=False)

        width = int(video_stream["width"])
        height = int(video_stream["height"])
        min_dim = min(width, height)
        fontsize = int(TextScale * min_dim)

        frame_rate = None
        if 'avg_frame_rate' in video_stream:
            fr = video_stream['avg_frame_rate']
            if '/' in fr:
                num, den = fr.split('/')
                frame_rate = float(num) / float(den)

        bitrate = video_stream.get('bit_rate', None)

        # 纵向文字
        if TextDirection == 1:
            LableContent = "\n".join(list(LableContent))

        # 位置表达式
        position_expr = {
            1: f"x=w-tw-10:y=h-th-10",
            2: f"x=10:y=h-th-10",
            3: f"x=w-tw-10:y=10",
            4: f"x=10:y=10",
            -1: f"x=(w-tw)/2:y=h-th-10",
            -2: f"x=(w-tw)/2:y=10",
            -3: f"x=10:y=(h-th)/2",
            -4: f"x=w-tw-10:y=(h-th)/2"
        }.get(PositionMode, "x=10:y=10")

        drawtext_args_base = {
            "fontfile": font_file,
            "text": LableContent,
            "fontsize": fontsize,
            "fontcolor": fontcolor,
            "x": position_expr.split(":")[0][2:],  # 去除 x=
            "y": position_expr.split(":")[1][2:],  # 去除 y=
            "alpha": "1"
        }

        video_input = ffmpeg.input(OriginalVideoPath)
        video_output = video_input

        for st in StartTime:
            drawtext_args = drawtext_args_base.copy()
            drawtext_args["enable"] = f"between(t,{st},{st + Duration})"

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


# 调用示例
result = EmbedVideoExplicitLabel(
    OriginalVideoPath='1.mp4',
    ResultFilePath='output.mp4',
    LableContent='人工智能合成',
    PositionMode=1,
    TextDirection=0,
    TextScale=0.05,
    TextColor=[255, 255, 255],
    FontName='黑体',
    Opacity=0.7,
    StartTime=[0],  
    Duration=5
)
print(result)

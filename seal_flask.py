import os
import tempfile
import json
import importlib
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

# 映射前端method到实际函数和模块
METHOD_MAP = {
    # 图片
    "EmbedImageImplicitLabel": ("image_metadata.image_metadata", "EmbedImageImplicitLabel", "image"),
    "DetectImageImplicitLabel": ("image_metadata.image_metadata", "DetectImageImplicitLabel", "image"),
    "EmbedImageExplicitLabel": ("image_explicit.image_explicit", "EmbedImageExplicitLabel", "image"),
    "DetectImageExplicitLabel": ("image_detection.main", "DetectImageExplicitLabel", "image"),
    # 视频
    "EmbedVideoImplicitLabel": ("video_metadata.video_metadata", "EmbedVideoImplicitLabel", "video"),
    "DetectVideoImplicitLabel": ("video_metadata.video_metadata", "DetectVideoImplicitLabel", "video"),
    "EmbedVideoExplicitLabel": ("video_explicit.video_explicit", "EmbedVideoExplicitLabel", "video"),
    "DetectVideoExplicitLabel": ("video_explicit.video_explicit", "DetectVideoExplicitLabel", "video"),
    # 音频
    "EmbedAudioImplicitLabel": ("audio_metadata.audio_metadata", "EmbedAudioImplicitLabel", "audio"),
    "DetectAudioImplicitLabel": ("audio_metadata.audio_metadata", "DetectAudioImplicitLabel", "audio"),
    "EmbedAudioExplicitLabel": ("audio_explicit.audio_explicit", "EmbedAudioExplicitLabel", "audio"),
    "DetectAudioExplicitLabel": ("audio_detection.audio_explicit_detector", "DetectAudioExplicitLabel", "audio"),
}

# 文件类型到mimetype
MIMETYPE_MAP = {
    "image": "image/png",
    "video": "video/mp4",
    "audio": "audio/wav"
}

@app.route('/seal_process', methods=['POST'])
def seal_process():
    try:
        # 获取文件和参数
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'No file uploaded'}), 400

        method = request.form.get('method')
        if not method or method not in METHOD_MAP:
            return jsonify({'error': 'Invalid or missing method'}), 400

        module_name, func_name, file_type = METHOD_MAP[method]
        mimetype = MIMETYPE_MAP.get(file_type, 'application/octet-stream')

        # 处理参数
        params = {}
        for k in request.form:
            if k not in ['method']:
                try:
                    params[k] = json.loads(request.form[k])
                except Exception:
                    params[k] = request.form[k]

        # 保存上传文件到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[-1]) as tmp_in:
            tmp_in.write(file.read())
            tmp_in.flush()
            input_path = tmp_in.name

        # 需要输出文件的接口，生成输出临时文件路径
        need_output = "Embed" in method
        output_path = None
        if need_output:
            fd, output_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[-1])
            os.close(fd)

        # 动态导入并调用
        module = importlib.import_module(f"{module_name}")
        func = getattr(module, func_name)

        # 参数拼装
        if "ImplicitLabel" in params:
            params["ImplicitLabel"] = json.dumps(params["ImplicitLabel"], ensure_ascii=False)
        if "ExplicitLabel" in params and isinstance(params["ExplicitLabel"], dict):
            params["ExplicitLabel"] = params["ExplicitLabel"]

        # 调用
        if need_output:
            # 嵌入类接口
            if "ImplicitLabel" in params:
                result_json = func(input_path, params["ImplicitLabel"], output_path)
            elif "ExplicitLabel" in params:
                result_json = func(input_path, output_path, params["ExplicitLabel"])
            else:
                result_json = func(input_path, output_path)
        else:
            # 检测类接口
            result_json = func(input_path)

        # 读取输出文件内容
        file_bytes = None
        if need_output and os.path.exists(output_path):
            with open(output_path, "rb") as fout:
                file_bytes = fout.read()

        # 清理临时文件
        os.remove(input_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

        # 返回
        if need_output and file_bytes is not None:
            # multipart 返回文件和json
            boundary = "SealBoundary"
            parts = []
            # part 1: 文件
            parts.append(
                f'--{boundary}\r\n'
                f'Content-Type: {mimetype}\r\n'
                f'Content-Disposition: form-data; name="file"; filename="result{os.path.splitext(file.filename)[-1]}"\r\n\r\n'
            )
            parts.append(file_bytes)
            # part 2: 结果json
            parts.append(
                f'\r\n--{boundary}\r\n'
                'Content-Type: application/json; charset=utf-8\r\n'
                'Content-Disposition: form-data; name="result"\r\n\r\n'
            )
            parts.append(result_json)
            parts.append(f'\r\n--{boundary}--\r\n')

            def generate():
                for part in parts:
                    if isinstance(part, bytes):
                        yield part
                    else:
                        yield part.encode('utf-8')
            return Response(
                generate(),
                mimetype=f'multipart/form-data; boundary={boundary}'
            )
        else:
            # 检测类接口直接返回json
            return Response(result_json, mimetype="application/json")

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=14000,threaded=True,debug=True)
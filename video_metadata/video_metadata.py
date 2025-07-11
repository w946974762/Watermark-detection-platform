import subprocess
import json
import os
import re

class VideoMetadataHandler:
    """
    根据TC260标准实践指南，实现视频元数据隐式标识的嵌入与检测。
    本实现通过调用外部 ffmpeg 程序来完成。
    """

    def __init__(self):
        """
        初始化处理器并检查ffmpeg是否可用。
        """
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """
        检查系统中是否安装了ffmpeg。
        """
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("错误: ffmpeg 未安装或未在系统PATH中。请先安装ffmpeg。")
    def DetectVideoImplicitLabel(self,video_path: str) -> str:
        """
        检测视频文件元数据中嵌入的隐式标识信息。

        参数:
            video_path (str): 待检测的视频文件路径。

        返回:
            str: JSON 字符串，包含检测结果和合规性判断。
        """
        return self._DetectVideoImplicitLabel(video_path)
    def EmbedVideoImplicitLabel(self,original_video_path: str, implicit_label: str, result_file_path: str) -> str:
        """
        将隐式标识信息嵌入至视频的元数据中。支持MP4, MOV, AVI, MKV, FLV等格式。

        参数:
            original_video_path (str): 原始视频文件路径。
            implicit_label (str): 隐式标识信息，JSON 格式的字符串。
            result_file_path (str): 嵌入标识后视频的输出路径。

        返回:
            str: JSON 字符串，报告处理结果。
        """
        return self._EmbedVideoImplicitLabel(original_video_path, implicit_label, result_file_path)

    def _EmbedVideoImplicitLabel(self,original_video_path: str, implicit_label: str, result_file_path: str) -> str:
        """
        实际实现嵌入视频隐式标识的逻辑。
        """
        if not os.path.exists(original_video_path):
                return json.dumps({
                "status": -2,
                "result": f"执行错误: 输入文件不存在 '{original_video_path}'"
            })
                
        # 验证 implicit_label 是否为合法的JSON
        try:
            json.loads(implicit_label)
        except json.JSONDecodeError:
            return json.dumps({
                "status": -1,
                "result": "嵌入失败: 'implicit_label' 不是一个有效的JSON字符串。"
            })

        # 构建ffmpeg命令
        # -map_metadata 0 用于从输入文件复制全局元数据
        # -metadata "AIGC=..." 用于设置新的元数据标签
        # -c copy 用于直接复制流，不做重新编码，速度快且无损
        command = [
            "ffmpeg",
            "-y",
            "-i", original_video_path,
            "-map_metadata", "0",
            "-metadata", f"AIGC={implicit_label}",
            "-c", "copy",
        ]
        
        # 根据标准，MP4/MOV格式需要一个特殊标志
        if original_video_path.lower().endswith(('.mp4', '.mov')):
            command.extend(["-movflags", "use_metadata_tags"])
            
        command.append(result_file_path)

        try:
            # 运行命令，如果文件已存在则覆盖
            subprocess.run(
                command if os.path.exists(result_file_path) else command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return json.dumps({
                "status": 1,
                "result": f"嵌入成功，文件已保存至 '{result_file_path}'"
            })
        except subprocess.CalledProcessError as e:
            return json.dumps({
                "status": -1,
                "result": f"嵌入失败: ffmpeg执行出错。\n{e.stderr.decode('utf-8', 'ignore')}"
            })
        except Exception as e:
            return json.dumps({
                "status": -2,
                "result": f"执行错误: {str(e)}"
            })


    def _DetectVideoImplicitLabel(self,video_path: str) -> str:
        """
        实际实现检测视频隐式标识的逻辑。
        """
        if not os.path.exists(video_path):
                return json.dumps({
                "status": -2,
                "result": f"执行错误: 输入文件不存在 '{video_path}'"
            })

        try:
            # ffmpeg将信息打印到stderr
            result = subprocess.run(
                ["ffmpeg", "-i", video_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # 使用正则表达式从ffmpeg的输出中查找AIGC标签
            # 匹配 "AIGC" 后面跟冒号，然后捕获花括号内的所有内容
            match = re.search(r"AIGC\s*:\s*(\{.*\})", result.stderr)
            
            if not match:
                return json.dumps({
                    "status": -1,
                    "result": "未检测到隐式标识 'AIGC'。",
                })
            
            aigc_json_str = match.group(1)
            
            # 解析JSON并检查合规性
            try:
                label_data = json.loads(aigc_json_str)
                compliance_result, final_label_list = self._check_compliance(label_data)
                
                return json.dumps({
                    "status": 1,
                    "result": "检测成功",
                    "ImplicitLabel": final_label_list
                })
            except json.JSONDecodeError:
                    return json.dumps({
                    "status": -1,
                    "result": f"检测到'AIGC'标签，但其内容不是有效的JSON: {aigc_json_str}",
                })

        except Exception as e:
            return json.dumps({
                "status": -2,
                "result": f"执行错误: {str(e)}"
            })

    def _check_compliance(self, label_data: dict) -> tuple[bool, list]:
        """
        辅助函数，检查检测到的数据是否符合规范。
        规范要求包含指定的7个字段。
        """
        if not isinstance(label_data, dict):
            return False, []

        expected_keys = {
            "Label", "ContentProducer", "ProduceID", "ReservedCode1",
            "ContentPropagator", "PropagateID", "ReservedCode2"
        }
        
        detected_keys = set(label_data.keys())
        is_fully_compliant = expected_keys.issubset(detected_keys)
        
        final_label_list = []
        for key in expected_keys:
            value = label_data.get(key, "N/A") # 如果键不存在，则值为"N/A"
            is_key_compliant = key in detected_keys
            final_label_list.append([key, value, is_key_compliant])
            
        return is_fully_compliant, final_label_list

def DetectVideoImplicitLabel(video_path: str) -> str:
    """
    检测视频文件元数据中嵌入的隐式标识信息。

    参数:
        video_path (str): 待检测的视频文件路径。

    返回:
        str: JSON 字符串，包含检测结果和合规性判断。
    """
    handler = VideoMetadataHandler()
    return handler.DetectVideoImplicitLabel(video_path)
def EmbedVideoImplicitLabel(original_video_path: str, implicit_label: str, result_file_path: str) -> str:
    """
    将隐式标识信息嵌入至视频的元数据中。支持MP4, MOV, AVI, MKV, FLV等格式。

    参数:
        original_video_path (str): 原始视频文件路径。
        implicit_label (str): 隐式标识信息，JSON 格式的字符串。
        result_file_path (str): 嵌入标识后视频的输出路径。

    返回:
        str: JSON 字符串，报告处理结果。
    """
    handler = VideoMetadataHandler()
    return handler.EmbedVideoImplicitLabel(original_video_path, implicit_label, result_file_path)
# --- 使用示例 ---
if __name__ == "__main__":
    # 0. 准备工作
    # 请确保您有一个名为 'input.mp4' 的视频文件在此脚本同目录下
    # 或者修改下面的文件路径
    input_video = "input.mp4"
    output_video_with_label = "output_labeled.mp4"
# 图像水印工具

这是一个 Python 脚本，用于在给定的图片上嵌入可视化的水印文字。脚本支持多种自定义选项，包括水印内容、位置、颜色、字体、大小和透明度。

## 功能特性

- **多种预设内容**: 支持四种预设的水印内容选项。
- **高度可定制**: 可自定义水印的位置、方向、颜色、大小和透明度。
- **支持本地与远程图片**: 可以处理本地文件路径或网络图片 URL。
- **JSON 格式返回**: 脚本执行结果以 JSON 字符串形式返回，便于程序调用。

---

## 1. 环境设置

在运行脚本之前，您必须设置好 Conda 环境并安装所需的依赖包。

### 步骤 1: 创建并激活 Conda 环境

如果您还未创建环境，请使用以下命令创建并激活一个名为 `watermark_env` 的新环境。

```bash
# 创建环境 (仅需一次)
# conda create -n watermark_env python=3.11 -y

# 激活环境 (每次使用前都需要)
conda activate watermark_env
```
> **重要**: 在您的服务器环境中，激活命令可能是 `source /home/scl1999/miniconda3/bin/activate watermark_env`。

### 步骤 2: 安装依赖

在**激活环境后**，使用 pip 安装所有必要的 Python 库。

```bash
pip install -r requirements.txt
```

### 步骤 3: 准备字体

脚本需要一个中文字体文件来渲染水印。请确保在项目目录下有一个 `fonts` 文件夹，并且里面包含一个名为 `msyh.ttc` 的字体文件。
（已完成）
---

## 2. 如何运行脚本

### 基本用法

使用默认参数在图片上添加水印。默认水印为白色的 "AI生成"，位于右下角。

```bash
python watermark.py <输入图片路径> <输出图片路径>
```
**示例:**
```bash
python watermark.py test.jpg output.png
```

### 高级用法：自定义参数

通过 `--ExplicitLabel` 参数可以详细定制水印的样式。该参数接收一个 JSON 格式的字符串。

**命令格式:**
```bash
python watermark.py <输入图片> <输出图片> --ExplicitLabel '<JSON配置>'
```

**可配置参数列表:**

| 参数名 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `ContentMode` | int | **(推荐)** 水印内容模式。 **1**: "人工智能生成", **2**: "人工智能合成", **3**: "AI生成" (默认), **4**: "AI合成". | `'{"ContentMode": 1}'` |
| `PositionMode` | int | 水印位置。 **1**:右下, **2**:左下, **3**:右上, **4**:左上, **-1**:下中, **-2**:上中, **-3**:左中, **-4**:右中. | `'{"PositionMode": 4}'` |
| `TextDirection` | int | 文字方向。**0**: 横向 (默认), **1**: 纵向. | `'{"TextDirection": 1}'` |
| `TextColor` | list | 文字的RGB颜色。 | `'{"TextColor": [255, 0, 0]}'` (红色) |
| `TextScale` | float | 文字大小，为图片短边高度的比例 (>= 0.05)。 | `'{"TextScale": 0.1}'` |
| `Opacity` | float | 透明度，范围从 0.0 (完全透明) 到 1.0 (完全不透明)。 | `'{"Opacity": 0.75}'` |
| `FontName` | int | 字体名称。 **1**:微软雅黑 (默认), **2**:宋体, **3**:黑体, **4**:Arial, **5**:Times New Roman. | `'{"FontName": 2}'` |
| `LableContent` | str | **(已弃用)** 直接提供文本内容。会被`ContentMode`覆盖。 | `'{"LableContent": "自定义内容"}'` |
注：ContentMode与LableContent关系：
当您运行脚本时，它会首先检查您是否在 --ExplicitLabel 中提供了 ContentMode。
如果提供了 ContentMode，脚本就会根据您给的数字（1, 2, 3, 或 4）选择对应的预设文字，并完全忽略 LableContent。
如果您没有提供 ContentMode，脚本才会接着去寻找 LableContent，并使用您在里面提供的自定义文本。

**组合示例:**

同时设置内容为 "人工智能合成" (模式2) 和颜色为黑色:
```bash
python watermark.py test.jpg output.png --ExplicitLabel '{"ContentMode": 2, "TextColor": [0, 0, 0]}'
```

---

## 3. 返回结果说明

脚本执行后会在终端打印一个 JSON 字符串，格式如下：

```json
{
  "status": 1,
  "result": "结果说明"
}
```
**Status 值说明:**
*   **1**: 嵌入成功。
*   **0**: 未嵌入 (此版本中未使用)。
*   **-1**: 嵌入失败 (通常是参数错误)。
*   **-2**: 执行错误 (通常是文件找不到或程序异常)。 
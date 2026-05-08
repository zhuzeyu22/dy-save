#!/bin/bash

cd "$(dirname "$0")"

echo "正在检查 ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "错误: ffmpeg 未安装"
    echo "请运行: sudo apt install ffmpeg  (Ubuntu/Debian)"
    echo "或:     brew install ffmpeg      (macOS)"
    exit 1
fi

echo "正在检查 Python 依赖..."
pip install -q -r requirements.txt

echo "正在安装 pyannote 模型..."
python -c "from pyannote.audio import Pipeline; Pipeline.from_pretrained('pyannote/speaker-diarization-3.1')" 2>/dev/null || echo "注意: pyannote模型需要HuggingFace访问令牌"

echo ""
echo "=========================================="
echo "  抖音直播录音系统"
echo "=========================================="
echo ""
echo "使用方法:"
echo "  1. 编辑 config.yaml 配置文件"
echo "  2. 设置抖音账号Cookie和Obsidian路径"
echo "  3. 运行: python dy_monitor.py"
echo ""
echo "按 Ctrl+C 优雅退出"
echo "=========================================="
echo ""

python dy_monitor.py

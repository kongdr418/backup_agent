#!/bin/bash
# 初始化脚本 - 安装依赖并启动服务

# 加载 .env 环境变量
if [ -f .env ]; then
    echo "📁 加载环境变量..."
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "📦 安装 Python 依赖..."
pip3 install -r requirements.txt -q

echo "📦 安装 Node.js 依赖..."
npm install

echo "🚀 启动服务..."
echo "服务地址: http://127.0.0.1:5000"
echo "按 Ctrl+C 停止服务"
echo ""

python3 app.py

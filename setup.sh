#!/bin/bash
# 项目初始化脚本 - 一键配置完整的开发环境

set -e  # 出错即停止

echo "🚀 B1500 项目初始化"
echo "================================"

# 检查Python版本
echo "📋 检查Python版本..."
python_version=$(python --version 2>&1 | grep -oP '\d+\.\d+' || echo "unknown")
echo "   Python版本: $python_version"

if ! python --version 2>&1 | grep -qE '(3\.10|3\.11|3\.12)'; then
    echo "⚠️  建议Python版本 >= 3.10"
fi

# 创建虚拟环境
echo ""
echo "📦 创建虚拟环境..."
if [ -d ".venv" ]; then
    echo "   ✅ .venv 已存在，跳过创建"
else
    python -m venv .venv
    echo "   ✅ 虚拟环境创建成功"
fi

# 激活虚拟环境
echo ""
echo "✨ 激活虚拟环境..."
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || {
    echo "   ⚠️  自动激活失败，请手动运行:"
    echo "   - Windows: .venv\\Scripts\\activate"
    echo "   - Linux/Mac: source .venv/bin/activate"
    exit 1
}
echo "   ✅ 虚拟环境已激活"

# 升级pip
echo ""
echo "🔧 升级pip..."
pip install --upgrade pip setuptools wheel -q
echo "   ✅ pip已升级"

# 安装依赖
echo ""
echo "📚 安装依赖包..."
if [ -f "requirements/dev.txt" ]; then
    pip install -r requirements/dev.txt
    echo "   ✅ 依赖安装完成"
else
    echo "   ⚠️  requirements/dev.txt 不存在"
    exit 1
fi

# 安装本项目包
echo ""
echo "🎯 安装项目包..."
pip install -e .
echo "   ✅ 项目包安装完成"

# 验证安装
echo ""
echo "✅ 验证安装..."
python -c "
import sys
try:
    import pyvisa
    import yaml
    import numpy
    import pandas
    import pytest
    print('   ✅ 所有核心依赖已安装')
    print(f'   Python: {sys.version.split()[0]}')
except ImportError as e:
    print(f'   ❌ 缺少依赖: {e}')
    sys.exit(1)
"

echo ""
echo "🎉 环境初始化完成！"
echo ""
echo "📝 后续步骤："
echo "   1. 连接B1500仪器"
echo "   2. 修改 configs/instruments.yaml 中的GPIB地址"
echo "   3. 运行: python scripts/verify_dc_sweep.py"
echo ""
echo "💡 下次打开项目时，运行以激活venv:"
echo "   - Windows: .venv\\Scripts\\activate"
echo "   - Linux/Mac: source .venv/bin/activate"
echo ""

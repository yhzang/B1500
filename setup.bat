@echo off
REM 项目初始化脚本 - 一键配置完整的开发环境（Windows版）

setlocal enabledelayedexpansion

echo.
echo 🚀 B1500 项目初始化 (Windows)
echo ================================
echo.

REM 检查Python版本
echo 📋 检查Python版本...
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "python_version=%%i"
echo    Python版本: %python_version%

REM 创建虚拟环境
echo.
echo 📦 创建虚拟环境...
if exist ".venv" (
    echo    ✅ .venv 已存在，跳过创建
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo    ❌ 虚拟环境创建失败
        exit /b 1
    )
    echo    ✅ 虚拟环境创建成功
)

REM 激活虚拟环境
echo.
echo ✨ 激活虚拟环境...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo    ⚠️  自动激活失败，请手动运行: .venv\Scripts\activate
    exit /b 1
)
echo    ✅ 虚拟环境已激活

REM 升级pip
echo.
echo 🔧 升级pip...
python -m pip install --upgrade pip setuptools wheel -q
echo    ✅ pip已升级

REM 安装依赖
echo.
echo 📚 安装依赖包...
if exist "requirements\dev.txt" (
    pip install -r requirements\dev.txt
    if errorlevel 1 (
        echo    ❌ 依赖安装失败
        exit /b 1
    )
    echo    ✅ 依赖安装完成
) else (
    echo    ⚠️  requirements\dev.txt 不存在
    exit /b 1
)

REM 安装本项目包
echo.
echo 🎯 安装项目包...
pip install -e .
if errorlevel 1 (
    echo    ❌ 项目包安装失败
    exit /b 1
)
echo    ✅ 项目包安装完成

REM 验证安装
echo.
echo ✅ 验证安装...
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

echo.
echo 🎉 环境初始化完成！
echo.
echo 📝 后续步骤：
echo    1. 连接B1500仪器
echo    2. 修改 configs\instruments.yaml 中的GPIB地址
echo    3. 运行: python scripts\verify_dc_sweep.py
echo.
echo 💡 下次打开项目时，运行以激活venv:
echo    .venv\Scripts\activate
echo.

endlocal

#!/usr/bin/env python
"""
DC Sweep API Verification Script

验证DC扫描API的功能正常。提供了两种运行模式：
  1. 模拟模式(推荐):  无需硬件，直接验证API逻辑
  2. 硬件模式: 连接真实仪器进行完整功能验证

Usage:
    python scripts/verify_dc_sweep.py [--real]
        --real    连接真实仪器进行验证(需要硬件)
"""

import sys
import os
import argparse
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def demo_simulated():
    """演示1: 无硬件模拟验证。"""
    print("\n" + "=" * 70)
    print("演示1: DC Sweep API - 模拟验证 (No Hardware)")
    print("=" * 70)

    from fefetlab.measurements.dc import (
        DCSweepConfig,
        DCSweepRunner,
        DCDataExporter,
    )
    import pandas as pd

    # 1. 配置
    print("\n[Step 1] 创建配置...")
    config = DCSweepConfig.from_notebooks_default(ch_g=4, ch_d=5, ch_s=6)
    print("✓ Config created:")
    print(f"  G=CH{config.channels['G'].channel}, "
          f"D=CH{config.channels['D'].channel}, "
          f"S=CH{config.channels['S'].channel}")

    # 2. 模拟B1500
    print("\n[Step 2] 创建模拟仪器...")

    class MockB1500:
        def __init__(self):
            self.voltages = {}

        def fmt(self, m):
            pass

        def av(self, c, m):
            pass

        def fl(self, m):
            pass

        def cn(self, chs):
            pass

        def dv(self, ch, vr, v, ic):
            self.voltages[ch] = v

        def ti(self, ch, ir=0):
            v = self.voltages.get(ch, 0)
            if ch == 4:
                return v * 1e-8
            elif ch == 5:
                return (v ** 2) * 1e-5 if v < 0 else 1e-6
            return 0.0

        def errx(self):
            return "0"

        def dz(self, chs):
            for ch in chs:
                self.voltages[ch] = 0.0

        def cl(self, chs):
            pass

    b1500 = MockB1500()
    print("✓ Mock B1500 created")

    # 3. 扫描
    print("\n[Step 3] 执行 Id-Vg 扫描...")
    runner = DCSweepRunner(b1500, config)
    vg_points = [0.0, -0.2, -0.4, -0.6, -0.8]
    df = runner.sweep_vg(vg_points=vg_points, vd_fixed=0.1, vs_fixed=0.0)
    print(f"✓ Sweep completed: {len(df)} points")

    # 4. 数据导出
    print("\n[Step 4] 导出数据和QC...")
    exporter = DCDataExporter()
    result = exporter.export_sweep(df, "verify_dc_api_demo")
    run_dir = result["run_dir"]
    print(f"✓ Data exported to: {run_dir}")
    print(f"  - {result['data_paths']['csv'].name}")
    print(f"  - {result['data_paths']['json'].name}")
    print(f"  - qc.csv")

    # 5. 查看数据
    print("\n[Step 5] 测量结果预览:")
    print("-" * 70)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print(df[["vg_set", "vd_set", "id_A", "ig_A", "status"]].to_string(index=False))
    print("-" * 70)

    # 6. QC报告
    print("\n[Step 6] QC报告:")
    print("-" * 70)
    qc_df = result["qc_df"]
    print(qc_df[["vg_set", "status", "issues"]].to_string(index=False))
    print("-" * 70)

    # 7. 清理
    print("\n[Step 7] 清理测试数据...")
    import shutil

    shutil.rmtree(run_dir)
    print("✓ Test directory cleaned")

    print("\n" + "=" * 70)
    print("✅ 模拟验证成功！API工作正常。")
    print("=" * 70)
    print("\n下一步：")
    print("  1. 使用真实硬件: python scripts/verify_dc_sweep.py --real")
    print("  2. 查看示例: notebooks/10_dc_api_idvg_example.ipynb 或 11_dc_api_idvd_example.ipynb")
    print("  3. 查看文档: src/fefetlab/measurements/dc/README.md")


def demo_real_hardware():
    """演示2: 连接真实仪器验证。"""
    print("\n" + "=" * 70)
    print("演示2: DC Sweep API - 真实硬件验证")
    print("=" * 70)

    import yaml
    from fefetlab.instruments.visa_session import VisaConfig, VisaSession
    from fefetlab.measurements.dc import DCSweepAPI

    # 加载配置
    print("\n[Step 1] 加载仪器配置...")
    try:
        with open("configs/instruments.yaml", "r", encoding="utf-8") as f:
            inst_cfg = yaml.safe_load(f)["b1500"]
        with open("configs/channel_map.yaml", "r", encoding="utf-8") as f:
            roles = yaml.safe_load(f)["current_device"]["role_map"]

        visa_cfg = VisaConfig(
            resource=inst_cfg["resource"],
            timeout_ms=inst_cfg["timeout_ms"],
            write_termination=inst_cfg["write_termination"],
            read_termination=inst_cfg["read_termination"],
            send_end=inst_cfg["send_end"],
        )

        ch_g = roles["G"]
        ch_d = roles["D"]
        ch_s = roles["S"]

        print("✓ Config loaded:")
        print(f"  Resource: {inst_cfg['resource']}")
        print(f"  Channels: G={ch_g}, D={ch_d}, S={ch_s}")

    except FileNotFoundError as e:
        print(f"❌ 找不到配置文件: {e}")
        print("   请确保运行于B1500根目录")
        return False

    # 连接仪器
    print("\n[Step 2] 连接仪器...")
    try:
        with VisaSession(visa_cfg) as session:
            idn = session.query("*IDN?")
            print(f"✓ 连接成功!")
            print(f"  IDN: {idn}")

            # 创建API并执行扫描
            print("\n[Step 3] 执行小范围 Id-Vg 扫描...")
            api = DCSweepAPI(session, ch_g=ch_g, ch_d=ch_d, ch_s=ch_s)

            result = api.run_idvg_sweep(
                vg_points=[0.0, -0.2, -0.4],
                vd_fixed=0.1,
                vs_fixed=0.0,
                auto_export=True,
                verbose=True,
            )

            df = result["df"]
            run_dir = result["run_dir"]

            print(f"\n✓ 扫描完成！数据保存到: {run_dir}")
            print("\n测量结果:")
            print("-" * 70)
            print(df[["vg_set", "vd_set", "id_A", "ig_A", "status"]].to_string(index=False))
            print("-" * 70)

    except Exception as e:
        print(f"❌ 仪器连接失败: {e}")
        print("   请检查:")
        print("   1. 仪器是否打开")
        print("   2. GPIB地址是否正确")
        print("   3. 通道映射是否正确")
        return False

    print("\n" + "=" * 70)
    print("✅ 真实硬件验证成功！")
    print("=" * 70)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="DC Sweep API Verification Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 模拟验证 (推荐新手)
  python scripts/verify_dc_sweep.py

  # 真实硬件验证
  python scripts/verify_dc_sweep.py --real
        """,
    )

    parser.add_argument(
        "--real",
        action="store_true",
        help="Connect to real hardware for verification",
    )

    args = parser.parse_args()

    if args.real:
        success = demo_real_hardware()
    else:
        demo_simulated()
        success = True

    print("\n")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

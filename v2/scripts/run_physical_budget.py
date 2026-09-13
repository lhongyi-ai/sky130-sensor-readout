#!/usr/bin/env python3
"""Save analytical physical constraints separately from simulated performance."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sensor_readout.physical_budget import make_physical_budget


def main():
    report = make_physical_budget()
    output = ROOT / "results/physical_budget.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    lines = ["# 真实器件信息驱动的预算检查", "", "这里是解析约束与风险筛查，不是芯片仿真成绩。", "",
        "## 反馈网络与噪声折叠", "",
        "实际采用电阻反馈时，信号增益 G 不等于噪声增益 1+G。350 Ω/端源阻抗既改变增益，也贡献热噪声。",
        "以下用满足全幅 2.5 µs 建立要求的理想单极点作比较，只统计输入/反馈电阻噪声，未含晶体管噪声。",
        "瞬时采样会把高于 50 kHz 的噪声折叠回来；全 Nyquist FFT 必须统计这些噪声。", "",
        "| 输入总电阻/端 | 增益 | 反馈电阻/端 | 电阻输出噪声 RMS | 仅电阻 SNR 上界 |", "|---|---:|---:|---:|---:|"]
    for row in report["resistor_noise_cases"]:
        total = row["source_resistance_per_leg_ohm"] + row["input_resistor_per_leg_ohm"]
        lines.append(f"| {total:g} Ω | {row['gain']} | {row['feedback_resistor_per_leg_ohm']:g} Ω | {row['full_nyquist_sampled_rms_v']*1e6:.2f} µV | {row['resistor_noise_only_snr_upper_bound_db']:.2f} dB |")
    lines += ["", "这是降低反馈阻值、联合设计采样隔离/滤波网络的依据，不是直接宣称某个新取值已达标。",
        "不能只将积分带宽从 50 kHz 改成 5 kHz 来宣布 SNDR 达标。", "", "## MIM 电容与参考端", "",
        "固定 PDK 的连续模型：3×3 µm MIM 单位为 19.845 fF；每侧 4096 单位为 81.28512 pF。",
        "双阵列裸极板面积为 73,728 µm²，绝不是核心面积。已另做最小单元 DRC/LVS 和电容提取，完整阵列仍需实布线。",
        "参考端并非零负载。JSON 保存了保守的切换电荷、瞬时电流、去耦和建立时间上界，实际值必须来自带源阻抗的瞬态测试。", "",
        "## 仍需真实电路完成", "",
        "晶体管热噪声/闪烁噪声、采样时变噪声、参考回路、比较器回踢、稳定性、功耗和完整版图寄生均不能由这些计算代替。", ""]
    (ROOT / "results/physical_budget_report.md").write_text("\n".join(lines))
    print(json.dumps({"status": "ANALYTICAL_CONSTRAINTS_GENERATED", "chip_qualified": False, "report": str(output)}))


if __name__ == "__main__":
    main()

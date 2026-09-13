# 旧 OTA 剩余 32 项：本地对应复跑

32 项本地 ngspice 对应测试已完成，另有两项差分参考。完整报告：

- [复现报告与曲线](reviews/20260913T062428272833Z/复现报告.md)
- [32 项逐项状态](reviews/20260913T062428272833Z/jobs32.csv)
- [机器可读结果](reviews/20260913T062428272833Z/review.json)
- [原始数据覆盖与 13 个 MOS 工作点对照检查](evidence_check_20260913T061726614895Z.json)

这不是学校 Cadence 新运行。保留学校实际导出的尺寸、扩散几何和测试连接，在本地开源模型中形成对照基线。学校 extra 的 32 项仍需实际运行和回传数据。

结果含真实性能失败：PSRR± 约 36.33/36.10 dB；0.1 V 网格内有效 ICMR 为 0.8～1.2 V；10/20 pF 扩展负载相位裕度约 53.77°/40.55°。噪声为 401.15 nV/√Hz @1 kHz、52.30 µV RMS（10 Hz～1 MHz），无旧 OTA 硬门限，并保留全部模型警告。

所有有效运行在 `runs/20260913T061726614895Z/`，同偏置差分参考在 `rejection_reference/20260913T061918108509Z/`。首次 smoke 的 PMOS 符号适配假失败也独立保留。原始旧 OTA、学校库和历史结果未修改。

`run_campaign.py` / `run_rejection_reference.py` 在已有本地 EDA 容器的 `/repo` 运行；`build_report.py` / `check_evidence.py` 在本地 Python + NumPy + Matplotlib 环境分析。**它们不是学校 Python 3.6.8 的上传包。** 重跑会建立新时间戳目录，旧结果可按源快照和哈希复核。

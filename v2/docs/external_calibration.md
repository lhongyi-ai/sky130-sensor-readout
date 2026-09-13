# 外部校准的数据入口

校准在电脑的软件中运行，不在芯片上。输入可以来自行为模型、ngspice 或后续 Spectre 的原始转换码；导入工具不会自动认可其物理证据级别。

CSV 必须有这些列：`instance_id,sample_id,gain,vdd_v,temperature_c,raw_code,sensor_input_v`。
`sample_id` 在该文件内唯一；`raw_code` 是 0～4095 的原始整数；`gain` 是 1、4、16。
`sensor_input_v` 是两端传感器电压之差，校准/验证时必须已知，日常应用时可以留空。
必须只导出采集/转换稳定后的有效输出，不得将复位期间或无效码混入。

在仓库根目录使用：

```sh
python3 v2/scripts/calibrate.py fit nominal_training.csv frozen_coefficients.json
python3 v2/scripts/calibrate.py apply raw_samples.csv corrected_samples.csv --coefficients frozen_coefficients.json
python3 v2/scripts/calibrate.py validate independent_holdout.csv holdout_report.json --coefficients frozen_coefficients.json
```

- 每实例、每增益只允许在 1.8 V / 27 °C 的 −80%、0、+80% 满量程各至少 4096 个样本拟合。
- 单个训练样本触及端码即拒绝；不能用平均值掩盖饱和。
- 验证点必须独立于训练点，各至少 2048 个样本。标称平均残差目标 ≤1 LSB，其余温压 ≤4 LSB。
- 同一个实例/增益跨温压必须使用原系数，不许重新拟合。工具拒绝拿另一个实例或另一档增益的系数代用。
- 输出同时保留原始码和未取整、未裁剪的校准码，以及换算的输入电压。超量程和漂移不会被软件隐藏。
- 已存在的输出文件不覆盖；选择新的文件名保存下一次试验。

测试点全部通过，也只证明这批输入点的结果。完整 45 组合、三档增益、噪声、动态精度、失配和后仿真必须另有证据，不能由校准报告代替。

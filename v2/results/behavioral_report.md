# V2 本地行为实验结果

仅为行为模型和预算，不是 SKY130 电路性能。
Cadence 暂停；M2 尚缺 PDK 可行性证据，不能记为完整通过。

## 假设预算下的采样结果

| 增益 | 输入频率 Hz | SNDR dB | ENOB |
|---|---:|---:|---:|
| 1 | 994.873 | 69.244 | 11.210 |
| 1 | 4998.779 | 69.262 | 11.213 |
| 4 | 994.873 | 69.044 | 11.177 |
| 4 | 4998.779 | 69.042 | 11.176 |
| 16 | 994.873 | 66.651 | 10.779 |
| 16 | 4998.779 | 66.671 | 10.783 |

这些数字依赖配置中的假设噪声/增益/失调参数，不能用于宣称芯片达标。
线性校准改善静态误差，不改变 SNDR；该不变性已自动检查。

## 独立静态校准验证

| 增益 | 校准前最大平均误差 LSB | 校准后 |
|---|---:|---:|
| 1 | 8.637 | 0.167 |
| 4 | 10.721 | 0.155 |
| 16 | 18.836 | 0.116 |

误差为多次采样后的平均值，不代表单次转换精度。测试点与标定点分离。

## 失败保留与证据边界

- assumed_nominal_sndr_targets_met: PASS
- assumed_nominal_calibration_targets_met: PASS
- allocated_settling_target_met: PASS
- rss_budget_allocations_fit: PASS
- ideal_linearity_passes: PASS
- cdac_negative_control_fails: PASS
- all_high_noise_controls_fail_sndr: PASS
- slow_settling_control_fails: PASS
- fixed_calibration_exposes_high_gain_drift: PASS
- pvt_matrix_not_fabricated: PASS
- no_calibration_or_holdout_clipping: PASS

PASS 在此表示检测程序正确识别了预设失败，并非芯片通过验收。
45 个工艺/温压点乘三档增益的 135 行仅为测试定义，全部仍为 NOT_RUN。

## 关键预算

- LSB：195.312500 µV；0.25 LSB：48.828125 µV。
- 采集窗口：2.500 µs；满幅阶跃的单极点时间常数上限：257.624 ns。
- 20 fF 单元仅为候选假设，对应每侧 81.92 pF；尚未证明版图实现或匹配。
- 噪声折叠、参考源动态负载、真实比较器、功耗、面积、版图及寄生仍待电路验证。

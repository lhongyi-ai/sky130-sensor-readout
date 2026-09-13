# 旧 OTA：13 点 PVT 复核与下一步

**运行完整，性能未全部通过。** 新运行的 48 项均正常结束，45 项通过、3 项失败；加上之前的标称条件，合计 52 项中 49 项通过、3 项失败。按四项必须全部通过统计，13 个条件中 10 个通过，P06、P07、P13 因阶跃建立未通过。

报告：`project1_basic_report_20260913T023544Z_5cc09eef.zip`  
报告 SHA256：`9730a427a344b5161dc5faf99dd3c573ed76f68c86a9de8893601e1079c6a3d3`  
运行包为 1.0.4p3，包清单 SHA256：`a77492fe2de2aee32ab9021c867bfb1b38a66ed6e5826b4c9e3a51211585336e`。

## 为什么有三项失败

输入脉冲在 0.8 V 和 1.2 V 之间切换，阶跃幅度为 0.4 V。原有 1% 建立要求是：输出在规定时间内进入目标值 ±4 mV，并持续保持在范围内。三项波形都已经稳定，但最终输出偏离目标，因此建立时间记为缺失、性能判为 FAIL。

| 条件 | 工艺／电源／温度 | 高电平误差 | 低电平误差 | 未通过的边沿 |
|---|---|---:|---:|---|
| P06 | TT／1.62 V／-20°C | +9.903 mV | +4.226 mV | 上升、下降 |
| P07 | TT／1.62 V／27°C | +5.025 mV | +2.812 mV | 上升 |
| P13 | TT／1.98 V／85°C | -5.741 mV | -4.424 mV | 上升、下降 |

例如 P06 的目标高电平为 1.200 V，输出稳定在 1.209903 V，高出 9.903 mV；目标低电平为 0.800 V，输出稳定在 0.804226 V，高出 4.226 mV。两者都超过 ±4 mV。末段数据已经近乎恒定，因此现有证据不支持通过原样重跑或单纯延长时间解决。

![失败条件与旧波形的误差对照](pvt_settling_failures.png)

绿色区域是允许的误差范围。蓝线为 Cadence，橙色虚线为冻结 ngspice；两者在稳态处几乎重合。纵轴放大至 ±12 mV，切换瞬间的大误差被裁切，完整波形仍保存在原报告中。

## 旧结果实际上也存在相同问题

| 条件 | 旧高电平误差 | 新高电平误差 | 旧低电平误差 | 新低电平误差 |
|---|---:|---:|---:|---:|
| P06 | +9.888 mV | +9.903 mV | +4.214 mV | +4.226 mV |
| P07 | +5.008 mV | +5.025 mV | +2.799 mV | +2.812 mV |
| P13 | -5.762 mV | -5.741 mV | -4.437 mV | -4.424 mV |

冻结的 `reference/pvt_summary.csv` 在这三行同时记录了 `pass_fail=PASS` 和 `settling_status=SETTLING_NOT_REACHED`，建立时间为空。查看项目现有 `scripts/analyze_day4.py` 的 PVT 总判定可见，它检查增益、带宽、相位裕度、功耗、转换速率等，没有把建立时间加入总判定。因而这个历史 PASS 不能解释为本次要求的四类测试全部通过。

本次已用当前一致的建立测量方法复算全部 13 份冻结瞬态波形，旧数据在同样三处未通过。原始 CSV、历史标签和报告均不修改，复核后的判定单独列在 `pvt_comparison.csv` 中。`historical_pass_fail` 仅是旧标签，不作为本次验收依据。

## 13 条件完整汇总

负载均为 5 pF 并联 100 kΩ。表内功耗取 0.9 V 共模的 OP 测试；阶跃初始共模为 0.8 V，其初始功耗会略有不同。

| 条件 | 工艺 | VDD | 温度 | 增益 dB | 环路 MHz | PM ° | 功耗 µW | 最差建立 ns | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| P01 | TT | 1.80 | 27 | 67.684 | 16.733 | 68.788 | 271.828 | 74.19 | PASS |
| P02 | FF | 1.80 | 27 | 67.114 | 17.212 | 70.239 | 270.782 | 71.66 | PASS |
| P03 | SS | 1.80 | 27 | 68.032 | 16.218 | 67.329 | 272.755 | 76.34 | PASS |
| P04 | FS | 1.80 | 27 | 67.452 | 16.153 | 67.182 | 271.627 | 76.07 | PASS |
| P05 | SF | 1.80 | 27 | 67.844 | 17.176 | 70.215 | 271.825 | 71.65 | PASS |
| P06 | TT | 1.62 | -20 | 68.326 | 18.451 | 71.964 | 240.634 | 未达到 | FAIL |
| P07 | TT | 1.62 | 27 | 67.141 | 16.457 | 68.847 | 242.922 | 未达到 | FAIL |
| P08 | TT | 1.62 | 85 | 65.540 | 14.536 | 66.077 | 245.525 | 78.97 | PASS |
| P09 | TT | 1.80 | -20 | 68.853 | 18.798 | 71.937 | 269.315 | 74.96 | PASS |
| P10 | TT | 1.80 | 85 | 66.112 | 14.758 | 65.993 | 274.718 | 99.26 | PASS |
| P11 | TT | 1.98 | -20 | 69.216 | 19.072 | 71.936 | 298.101 | 70.73 | PASS |
| P12 | TT | 1.98 | 27 | 68.059 | 16.955 | 68.758 | 300.830 | 95.77 | PASS |
| P13 | TT | 1.98 | 85 | 66.507 | 14.939 | 65.939 | 303.995 | 未达到 | FAIL |

所有条件下的 OP、AC 与旧单环路测试通过；上升／下降转换速率通过。最低差分增益为 65.54 dB，最低环路单位增益频率为 14.536 MHz，最低相位裕度为 65.94°，最大 OP 供电功耗为 304.00 µW。通过范围仍是旧 OTA 的指标，不是新版前端或 ADC 的指标。

## 本地核对内容与限制

- 报告解压文件逐一与 ZIP 核对；上次报告的 272 份运行文件均原样保留。
- 用版本化本地源码还原 1.0.4p3，校验清单；52 项均重新核对原生导出网表、参数、端口连接及实际执行输入。全部任务的 OTA 核心网表相同，模型入口哈希一致。
- 全部 52 项 CSV 重新分析，与学校 metrics.json 一致，允许的差异仅为跨平台浮点舍入。没有改电路或放宽指标。
- 26 组 AC/环路记录均为 1081 点，覆盖 1 Hz～1 GHz；13 组瞬态记录均完整覆盖 0～5 µs，最大步长不超过 0.5 ns。各任务含 13 个 MOS 的完整有限工作点记录。
- 新增 48 项 Spectre 均为 0 errors、0 warnings；其中 24 项有 3 条 notices、24 项有 4 条 notices，数值求解提示如实保留。
- P01 OP 是此前 PSF 的导出恢复，其余 PVT 为学校实际运行。本地未执行 Cadence，也不能核验学校模型依赖文件、许可证或 OA 数据库。OCEAN 数值退出码未单独存档，依据返回状态、日志、完成标志和实际数据核对导出。
- 稳态误差的器件级成因尚未分解。现有证据说明它与旧设计相同，不能据此把所有差异归咎于某个器件、尺寸取整或求解器。
- 没有进行工艺补偿元件替换、失配、动态噪声、版图或完整系统验收。

## 下一步：补齐现有额外测试

继续既有旧 OTA 基础测试范围，先完成性能记录。保持三项失败，不重新生成电路，不需要新补丁。

**执行位置：学校 Linux 终端。** 复制整行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --group extra
```

这个组共 32 项，依次覆盖共模响应、电源扰动响应、普通小信号噪声、直流跟随范围、四种额外负载（1/2/10/20 pF）的环路与阶跃，以及 19 个输入共模工作点。它们用于记录旧 OTA 的适用范围；普通噪声测试不等于 ADC 开关动态噪声测试。

`PASS REVIEW_REQUIRED` 表示仿真和导出已完成，但该项没有自动数值验收门槛或需要结合其他数据分析；不等于性能 PASS。共模／电源扰动导出的传递响应也不能直接叫作 CMRR／PSRR，后续需要同频差分增益进行换算。输入共模范围边缘可能出现真实性能失败，保留后继续；遇到工具、网表或导出错误，程序会停止。

命令结束或停止后，执行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

下载并回传最后输出路径对应的 ZIP。此次不加 `--retry`，不执行 `create.il`，不修改原基准。完成复现记录后再针对真实缺陷讨论设计修订；PVT 三项未通过仍阻止“旧 OTA 全指标达标”的结论。

## English technical summary

All 48 additional PVT simulations completed normally with zero Spectre errors and warnings. Together with the retained nominal results, 49 of 52 jobs pass the current legacy acceptance criteria; P06_step, P07_step and P13_step fail 1% settling because their settled output errors exceed ±4 mV. Reanalysis of frozen ngspice waveforms reproduces the same failures. The historical aggregate PASS label does not include settling in its decision and must not be used as full qualification. All 13 conditions pass OP, differential AC and legacy single-loop criteria. The original netlists, results and historical labels are preserved. Further characterization may proceed with the existing extra group; full PVT performance qualification remains failed.

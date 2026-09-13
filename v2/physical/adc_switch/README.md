# SAR 采样开关：真实器件、独立版图及失败迭代

本目录不使用 Cadence。它只验证一个输入采样开关，不是整个 SAR ADC
或读出芯片的版图、线性、噪声及精度验收。

## 最终冻结结果

**独立四管采样开关的规定条件验证通过。** 正式入口是
`results/sampling_switch_release.json`，文件和端口索引见 `SOURCE_INDEX.md`。
最终参数：主 N-LVT 4/0.15µm、P-LVT 8/0.35µm，补偿管各半宽。

| 验证项 | 结果 |
|---|---|
| 实体版图 | DRC=0，LVS唯一匹配，95R/51C真实提取 |
| 实际单元边界/面积 | 16.0×17.295µm，276.72µm² |
| 全网格 | 45PVT×3输入×3共模×3驱动电阻×2视图=2430条件点，0失败 |
| 窗口/负载 | 2.476847754µs采集，保持至10µs，81.28512pF/端 |
| 原理图最坏采集/最终保持误差 | 10.94µV / 30.76µV |
| RC后最坏采集/最终保持误差 | 13.66µV / 26.15µV |
| 相反满量程初值边界 | 4个明确PVT的216条件点全通过；最坏采集22.15µV |

每项上述采集/保持误差均低于48.828125µV检查阈值。全网格是在45个
瞬态批次里放置电气独立副本，**不是2430次独立仿真命令，更不是随机
良率样本**。满量程边界的4个PVT没有伪装成另一轮45PVT。
`qualify_release.py` 重新读取全部45批原始波形，检查完整时长、有限值、
单调时间和逐点测量，并逐项核对网格；压缩波形全量保留在 `evidence/`。

仍使用理想1ns互补时钟边沿；采集窗口取自真实相位发生器的保守实测值。
系统还须验证实际时钟负载/偏斜、真实底板切换、噪声与ADC非线性。
本结果既不是全ADC通过，也不是Cadence/硅测结果。

## 已冻结的标准阈值基线

原电路是 `adc_tgate A B EN ENB VDD VSS`：标准 NFET W/L=8/0.15µm、
标准 PFET W/L=16/0.15µm。生成了真实带体接触/护环的 SKY130 PCell
版图、金属布线及端口，Magic DRC=0，Netgen LVS 唯一匹配。
平坦化后在新 Magic 进程中提取 42 个电阻、29 个正电容；没有用假电阻
或仅原理图电容冒充 RC 提取。对应文件位于 `artifacts/`。

2.5µs 采集、4096×3µm×3µm MIM 负载的 45PVT×3输入、额外标称
0/1kΩ 源阻抗，共 141 组原理图/RC 配对、282 次仿真已完成。
**14 个 view-case 未通过**，最坏 SF/1.62V/−20°C、输入1.01V 的
RC 采集残差约 −37.4mV。原理图同样失败，原因是低电源低温时两管
导通能力不足，不是后仿真凭空出现的问题。不能把 DRC/LVS 通过说成
该采样开关满足系统精度。

完整原始失败表：`results/switch_validation.json`。`run.py` 可重新生成；
它在指标失败时返回非零状态，结果不会被隐藏。

## 独立候选与已完成的对照

所有候选放在 `candidates/`，没有覆盖 ADC 负责人的 `adc_blocks.spice`。

| 候选 | 真实测试发现 |
|---|---|
| 只把 N 换为 LVT，仍 W8/P16 | SS低电压低温最大 Ron 从42.4kΩ降到16.0kΩ，仍约10mV建立误差；不足 |
| 双 LVT，N8/.15、P16/.35 | 最坏 Ron 降到约1.26kΩ，但关断注入可达195µV；速度好不等于精度好 |
| 双 LVT，N4/.15、P4/.35 | 注入下降，但SS建立残差约87µV；器件过小 |
| 双 LVT，N4/.15、P5/.35 | 旧2.5µs窗口141点中140通过，FS/1.98V/85°C高输入49.03µV略超48.83µV；不算全通过 |

注意：PDK 的低阈值 PMOS 最小合法/建模长度是0.35µm。早期尝试
0.15µm直接被模型拒绝，相关日志保留；没有在模型范围之外外推。
MIM 负载用实际 AC 电流核实为81.28512pF，`m` 与 `mult` 均按已验证的
PDK 调用规则传入。延长至完整7.5µs保持并反向切换外部输入后，旧候选
保持漏电的量级约0.04µV，主要问题是导通和关断电荷，不是这个保持区间的漏电。

N4/P5 两管候选也完成了独立实体版图，边界8.155×7.19µm，
58.63445µm²，DRC=0、LVS唯一匹配、42R/29C。9个旧窗口标称/极角
点的18次原理图/RC仿真通过，只证明这些已测试条件。
文件见 `artifacts/dual_lvt_rc_smoke/`，真实渲染图见同目录PNG。

## 最终窗口和扩展范围

真实相位生成器给出的最短采集窗口是2.476847754µs；旧2.5µs结果
不能冒充覆盖该较短窗口。`batch_qualification.py` 使用此窗口，测量关断
开始前1ns的采集误差，并保持至10µs；输入在关断后200ns反向切换。
每个PVT中独立复制相同电路，同时覆盖输入−0.2/0/+0.2V、共模偏移
−50/0/+50mV、源阻抗0/350/1000Ω。批量只是减少重复读入PDK的开销，
每个副本仍有自己的真实MOS、MIM负载和源电阻。

350Ω是冻结的主规格源阻抗，0/1kΩ属于额外敏感性测试。报告分别统计
主规格失败和敏感性失败。关断后的绝对四分之一LSB检查是额外设计余量；
它既不能代替全ADC线性/噪声检查，也不能代替固定系数外部校准的验证。
带半宽 dummy 的候选也仅是候选：不得假设理想电荷抵消。

四管版本的端口 **不再对称**：A是驱动源侧，B是保持电容/顶板侧。
dummy两管只短接到B。若系统把它作为VCM顶板钳位器，必须A接VCM、
B接顶板；不能沿用旧两管TG可随意交换A/B的习惯。钳位器承受真实
CDAC底板切换的行为仍由系统级仿真验证，不能仅用本目录的A端电压阶跃替代。

这里的电阻直接放在独立采样开关的输入端，是测试驱动器的等效电阻。
系统规格中的350Ω传感器源阻抗位于PGA之前；本测试不能代替传感器—PGA
闭环—采样器的真实联合驱动分析，也没有宣称PGA输出电阻就是350Ω。

## 复现

在项目已有离线工具容器 `/repo` 中运行，例如：

```sh
python3 v2/physical/adc_switch/run.py --tag new_standard --suite full
python3 v2/physical/adc_switch/characterize_candidate.py --tag new_lvt --suite full --model adc_tgate_dual_lvt --wn 4 --wp 5
python3 v2/physical/adc_switch/physical_candidate.py --tag new_layout --suite smoke --wn 4 --wp 5
python3 v2/physical/adc_switch/batch_qualification.py --tag new_short_window --suite full --wn 4 --wp 5 --physical-run new_layout
```

以上命令重现历史两管对照；最终四管的完整复现顺序是：

```sh
python3 v2/physical/adc_switch/physical_candidate.py --tag dummy_layout_final --suite physical_only --model adc_tgate_dual_lvt_dummy --wn 4 --wp 8
python3 v2/physical/adc_switch/batch_qualification.py --tag dummy_w4w8_rc_full --suite full --model adc_tgate_dual_lvt_dummy --wn 4 --wp 8 --physical-run dummy_layout_final
python3 v2/physical/adc_switch/fullscale_check.py
python3 v2/physical/adc_switch/qualify_release.py
```

这些固定tag适合全新克隆的工作目录；已有本地run时不要覆盖，需使用
独立副本或更新审核脚本的run选择。后处理脚本使用NumPy；最终资格只开
一个仿真worker，避免与其他模拟任务竞争内存。

必须使用新tag，不能覆盖过去的原始失败记录。`runs/` 保存每次输入网表、
日志、波形数据和哈希，默认不加入Git；`results/` 和筛选后的 `artifacts/`
是可携带证据。需安装同一公开PDK版本；本目录不复制PDK、规则文件或许可证密钥。

仍需系统集成的事项包括真实时钟驱动及偏斜、动态CDAC参考切换、匹配、
噪声、差分ADC线性和全链路精度。独立开关的通过不能替代这些验证。

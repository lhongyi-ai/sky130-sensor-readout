# 实际 SAR ADC 静态验证：可恢复批处理与完整性门禁

**状态：验证基础设施已实现；完整 ADC 全码线性尚未完成。**

这里不是 CDAC 电荷守恒计算，也不是输入一给定就直接输出理想码的行为 ADC。
每次转换都由原 `sar_controller.v` 实时读取真实 SKY130 比较器结果，
再控制下一位的真实参考开关与电容阵列。没有修改核心 RTL，也没有改变冻结的模拟电路。

## 冻结对象和外部条件

固定选择 `integration/candidates/20260908T045601001817Z` 的组合候选：

- 底板采样、真实连续时间前置放大器、动态比较器及保持锁存器。
- 按电容位权定尺寸的双 LVT 参考／采集开关。
- 两个顶板夹位使用独立物理模块的四 MOS dummy 补偿开关，方向未交换。
- 原 SAR RTL、原 `sensor_phases.spice` 晶体管相位发生器。
- 数字与模拟之间仍用理想逻辑电压桥；没有映射数字单元的延时或功耗。

每个 campaign 冻结全部上述源码、桥接资格报告、运行器及其 SHA256。
运行时另记录 ngspice/Verilator 版本、PDK 的解析路径和 combined 模型目录所有文件哈希。
不复制 PDK、规则或许可证。没有前端、模拟版图寄生、失配或器件随机噪声。

默认是 TT、1.8 V、27°C、每端 350 Ω 输入源、参考每端 1 Ω 加外部 10 nF。
参考 `tracking` 为 VDD/2 ± 0.2 V；`fixed` 为 1.1/0.7 V。两者有独立配置，
不得把一种模式的通过推广到另一种。当前没有覆盖完整 45 PVT。

## 三种证据严格分开

| Stage | 所需输入点 | 能说明什么 | 不能说明什么 |
|---|---:|---|---|
| `smoke` | 明确列出的少量点 | 接口、逐次逼近和局部输出 | 全码、INL/DNL、有效精度 |
| `centres` | 4096 个理想码中心 | 这一输入网格的输出覆盖 | 转换阈值和码宽，不能冒称线性通过 |
| `ramp` | 默认每 LSB 32 步，共 131073 点 | 完整后可给出 4095 个转换阈值区间及静态线性界限 | 噪声、失配、动态 SNDR 或完整 ADC 验收 |

`ramp` 的 INL 用实际 T1、T4095 作端点直线；内部码 1…4094 的 DNL
用端点拟合 LSB 归一化，和项目主分析器口径一致。两个饱和端码不具有
无界外部电压下的有限码宽，因此另要求在规定输入范围内实际观察到 0 和 4095。
按 ±0.4 V 截断的名义 LSB 码宽也保留，但只是边界诊断，不混称内部 DNL。

阈值不直接取单个浮点数：保存最后一个低码输入和第一个高码输入构成的区间，
把区间不确定度传播到 INL/DNL。只有整个误差区间都在目标内才标记
`GRID_STATIC_LIMITS_PASS`；区间跨过限值则是 `GRID_RESOLUTION_INCONCLUSIVE`。
即使网格通过，仍标记数值收敛未验证，`complete_adc_qualified` 始终为 false。

## 连续转换及恢复语义

一个 campaign 只构建一次真实 RTL 动态库。一个 batch 在同一 ngspice 进程内
连续完成多次 100 kS/s 转换，而不是每个输入点重新加载 PDK、重新编译或重置电路。

- 输入在前次真实 `data_valid` 后约 10 ns 开始改变，1 ns 完成，位于下一次采集窗口。
- 默认每个输入先丢弃一个转换，再保留一个转换，以暴露并缓解前值历史影响。
- batch 之间会重新求工作点并复位，因此显式重放前一个输入点，随后执行同样预热。
  **这仍然是有限历史协议，不能冒充从不重置的无限连续 ramp。**
- 根据 SPICE 时间轴核对所有 `data_valid`，不用 Verilator shim 中可能恒为零的 `$realtime`。
- 从 SPICE 实际 12 位输出电压总线重新解码，必须和 RTL 日志一致。
- 超时日志即便已有正确码，也不能算完整批次；保留原日志和所有尝试。
- `worker.lock` 限制一个 campaign 仅一个 worker。当前共享容器也只安排一个 ADC ngspice worker。

`baseline` 是 reltol=1e-5、vntol=10 nV、abstol=0.1 pA、最大步长 2 ns；
`strict` 是 reltol=1e-6、vntol=1 nV、abstol=0.01 pA、最大步长 1 ns。
这两个配置只是提供交叉数值检验入口；没有自动宣称一次较严格设置就是收敛证明。

## 运行方法

在 `sky130-v2-resume-20260910` 容器中执行。每个新计划必须使用不存在的目录。
默认 `run` **只运行一个 batch**，不会意外启动数天的全范围测试。

```sh
python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py plan \
  /repo/v2/analog/adc/verification_20260910/campaigns/example_smoke \
  --stage smoke --inputs 0.123 -0.000048828125 0.000048828125 \
  --batch-size 3 --warmup 1

python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py run \
  /repo/v2/analog/adc/verification_20260910/campaigns/example_smoke \
  --max-batches 1 --timeout-seconds 900

python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py collect \
  /repo/v2/analog/adc/verification_20260910/campaigns/example_smoke
```

如果运行器后来修改，使用该 campaign 中冻结的
`frozen/static_campaign.py run|collect <campaign>`；新版本会拒绝套用新分析语义到旧 campaign。
`--retry-incomplete` 创建新 attempt，不覆盖失败。完整 batch 默认跳过。
中断若遗留 `worker.lock`，须先确认原 worker 已退出再移除该精确锁文件；不要并发抢占。

启动全范围前先记录短批吞吐并批准合理计算预算。以下命令仅创建计划、不开始大跑：

```sh
python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py plan \
  /repo/v2/analog/adc/verification_20260910/campaigns/full_centres \
  --stage centres --batch-size 8 --warmup 1
python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py plan \
  /repo/v2/analog/adc/verification_20260910/campaigns/full_ramp32 \
  --stage ramp --steps-per-lsb 32 --batch-size 8 --warmup 1
```

收集器会重新读原始波形，而非只相信 summary 的 PASS 字符串。
缺批、重复输入编号、修改过的源码／原始结果、未完成波形、计数不符，均不能通过完整性门禁。

## 本轮可复核证据

- `campaigns/nominal_static_subset`：计划 3 个输入，仅首个输入实际完成，故返回
  **INCOMPLETE_COVERAGE，1/3**；0.123 V 的完整一次转换为 2677，SPICE 输出总线一致。
  12 µs 瞬态整个进程耗时 **43.079 s**，不能用这个值冒充单独 transient CPU 时间。
- `campaigns/continuous_three_point`：**同一进程中 6 次真实转换全部完成**，
  原始输出为 `[2677,2677,2047,2047,2048,2048]`。对应输入分别为
  0.123 V、−48.828125 µV、+48.828125 µV，每个重复两次；保留后一次。
  三个保留码都与理想码相同，coverage 为 **3/3，SMOKE_POINTS_COMPLETE_NOT_LINEARITY**。
  这是连续输入变化与局部阈值证据，不是全码或噪声精度通过。
- `test_static_campaign.py`：13 项合成数据软件测试，包括丢码、非单调、非线性、
  改计划、缺覆盖、超时以及实际输出总线不符时拒绝通过。
  **这些合成数据绝不是 SKY130 模拟结果。**
- `profile_runtime.py`：对一个已完成批次另跑相同电路的 OP-only 工作负载，记录
  编译、模型装载＋工作点进程耗时；用它估算瞬态耗时会明确标成外推而非直接测量。

### 实测运行成本，而不是假设马上能跑完整套

连续六次转换的 **62 µs** 波形实际耗时 **210.515 s**；RTL 编译一次 **0.592 s**。
单独启动相同 ADC 的 model-load＋OP 进程耗时 **2.836 s**，据此相减得到的
瞬态及输出耗时约 **207.679 s** 是估计，不是对求解器内部 CPU 时间的直接测量。
第一次 OP-only 夹具未保存所打印节点，因此计时资格标失败；原始记录保留，
第二次只修正 `.save` 列表后成功，不改模拟电路。

按这三个输入的极小样本吞吐外推，batch=8、每点丢弃一帧并包含跨批重放时：

| 计划 | 单 worker、单个 PVT 条件估计 |
|---|---:|
| 4096 个码中心、8703 次转换 | 约 3.50 天 |
| 32 点/LSB ramp、278530 次转换 | 约 112.12 天 |

这些不是承诺工期；输入、工艺角、时步、收敛和机器负载都可能改变吞吐。
因此**没有启动长跑**。源码批处理已摊薄编译和 PDK 装载，但主要成本是实际瞬态求解。
后续应先评审经数值收敛检验的时步优化、或保持同等阈值不确定度的自适应搜索；
不能静默减少采样网格或用 CDAC-only 计算替代完整 SAR。

`summarize_evidence.py` 会重新运行冻结原始波形审计、执行软件测试并生成带哈希索引的
`results/<timestamp>/summary.json`，其中 `all_non_cadence_work_complete` 明确为 false。

## 后续有界时步加速实验：10 ns 没有获得整段波形数值资格

只进行了两轮真实仿真：新增 DAC／参考观测的 **2 ns 基线**和 **10 ns 最大步长对照**。
两者使用相同冻结模拟电路、核心 RTL、PDK、容差、输入序列、1 ns 时钟／输入沿和
62 µs 时长。只增加保存节点，并改变 `.tran` 的最大步长参数；没有运行 20 ns。

`timestep_results/20260910T063430835346Z/comparison.json` 为这对实验的最终判定，
`manifest.json` 是启动时的声明快照，不能把其初始 RUNNING 字段当最终状态。

| 对照项 | 2 ns | 10 ns |
|---|---:|---:|
| 实际整个进程时间 | 198.762 s | 179.991 s |
| 接受的波形点 | 96,923 | 75,132 |
| 小于 100 ps 的步数 | 60,704 | 60,699 |
| 六个输出码 | 2677,2677,2047,2047,2048,2048 | 完全相同 |

加速只有 **1.104×，用时下降约 9.4%**，不是最大步长比例对应的 5×。
2 ns 基线的中位步长只有 **12.08 ps**；47.2% 的步数集中在 evaluate 翻转后
20 ns 窗口内，而这些窗口仅占约 4.7% 的模拟时长。放宽上限主要减少平坦区采样，
切换附近的细步几乎不变。这是数值步密度证据，不是 CPU profiler：不能据此断言
`d_cosim`、牛顿迭代或拒绝步中哪一个占用了多少 CPU。

新增观测后的 2 ns 波形与旧波形的全部原有列逐元素完全一致，确认观测没有改变旧轨迹。
真正的模拟比较也不只检查码：

- 所有 72 次比较前，DAC 差分最大差 **2.066 nV**，低于预先规定的 0.05 LSB＝9.765625 µV。
- 比较前 RP/RN 最大差约 **9.95 pV**；全段公共 1 ns 网格上参考最大差约 **0.984 µV**。
- 六次有效输出与 72 次 evaluate 的时序比较均通过 1 ns 容差。
- **整个 DAC 波形公共网格最大差为 69.509 µV＝0.356 LSB，超过预设 0.05 LSB。**
  最坏发生在首轮采集 1.286 µs；后续转换中也存在超过 0.05 LSB 的短时差异。

因此最终状态是 **TIMESTEP_COMPARISON_FAIL**，默认仍是 2 ns，没有把 10 ns 升级为通用设置。
这表示该宽松时步没有满足本次整段波形数值对照，并不是说 ADC 已经获得或失去最终电气资格。

`summarize_timestep.py` 进一步区分相对 2 ns 参考曲线的重采样成分与残差。在最坏公共网格点，
单纯参考重采样贡献约 **0.167 µV**，其余残差约 **−69.675 µV**；不能把失败解释成纯插值假象。
试验仍不提供精确连续解，1 ns 网格也可能漏掉更窄毛刺。所有码相同和比较前的小误差，
只能作为这三个输入、这一工艺温压条件下的局部证据，不能证明全码、PVT、失配或噪声精度。

软件测试现在为 **16 项**（原 13 项＋3 项时步夹具测试）。两个真实实验均结束，
没有启动额外仿真或全码扫描。

### 最后一次电荷容差路线的前提检查：未启动变更试验

收到的有界试验前提是将 `chgtol=1e-18` 放宽到 `1e-17`。但冻结 ADC deck 没有
显式指定 chgtol；不能直接假设它使用了前端另一套测试台的容差。

先只加载电路打印选项，发现 ngspice 在分析前显示的是未初始化默认结构：
连 reltol 和积分方法都未应用 deck，因此这个结果不能作为有效运行时配置。
随后仅用同一冻结电路执行一次短 OP，再打印选项，确认：

| 有效选项 | 值 |
|---|---:|
| 积分方法 | GEAR |
| reltol | 1e-5 |
| abstol | 1e-13 A |
| vntol | 1e-8 V |
| **chgtol** | **1e-14 C** |
| trtol | 1，由 XSPICE 自动缩小 |

实际证据为 `option_probes/20260910T064511260501Z/native.log`，
探针程序为 `probe_options.py --after-op`。原始 deck、PDK、RTL 均未改变。

基线 **并不是 1e-18**，因此按任务的明确前提停止：**没有运行任何新容差瞬态**，
没有把 chgtol 改为 1e-17。相对于实际 1e-14，这将是收紧 1000 倍，而不是放宽 10 倍，
不能冒称在做原定加速实验。

## 还没有完成

没有完整 4096 码中心扫描、131073 点 ramp、跨数值设置收敛检查、45 PVT 静态覆盖、
真实时变器件噪声动态精度、完整 ADC 失配、前端联调或 ADC 版图/PEX。
这里是实际验证能力和小规模电路证据的推进，不能写成“全部不用 Cadence 的任务已完成”。

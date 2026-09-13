# project1：Cadence 迁移与验证

## 最新验证状态：2026-09-13 UTC 报告

当前学校执行版本为 `basic_design_v1_0_4` 加运行补丁 **1.0.4p3**。本包 **87 个既定入口都有实际运行证据，完整原版验收仍未完成**。最新 32 项额外测试全部执行/导出成功，原始标签为 **13 PASS、14 FAIL、5 REVIEW_REQUIRED**。10/20 pF 相位裕度分别为 53.77°/40.55°，未达到旧版 55°门槛。基础包 ICMR 使用 ≥50 dB 初筛；按原版“相对标称下降不超过 3 dB”等要求复核，仅 0.8～1.2 V 的五个已采样点通过，不能把初筛的 0.8～1.4 V 当作完整合格范围。静态噪声单位已核实：1 kHz 输入噪声 401.150 nV/√Hz，10 Hz～1 MHz 积分为 52.2998 µV RMS；原规格仅要求报告此项。

最新证据入口：[额外测试复核与下一步](reports/basic_20260913T062632Z_d7dc1ae6/额外测试复核与下一步.md)、[完整复核数据](reports/basic_20260913T062632Z_d7dc1ae6/review.json)、[结果图](reports/basic_20260913T062632Z_d7dc1ae6/extra_characterization.png)。最新报告 ZIP SHA256 为 `413e1edf9477d189f043045c2c49c17ef7900432de9b4e5962b545ee78822c27`。

原生旧 OTA 标称四项已通过，13 点 PVT 的 52 项中 49 项通过，P06_step、P07_step、P13_step 仍未通过 1% 建立要求。稳定后的跟随误差超过 ±4 mV，冻结 ngspice 波形也存在同样问题，历史总 PASS 没有纳入建立时间。证据见 [PVT 复核](reports/basic_20260913T023544Z_5cc09eef/PVT复核与下一步.md)。原报告和失败保持不变。

当前用户无需重跑 extra、PVT 或重建电路。下一份本地补充包（尚未生成）需要统一补齐相同工作点的 CMRR/PSRR、原版 ICMR 细扫描/判据、原版固定共模且正反向扫描的输出摆幅测试。工艺无源默认尺寸的 TT 复核通过；统计、物理流程等 M0 能力仍未完整验收。新版前端/ADC/版图与全系统性能尚未在 Cadence 完成验收。

**以下内容是早期过程与交付记录；其中“尚未运行”“当前最新”等描述保留当时语境，当前状态以上节及所链接的实际证据为准。**

2026-09-11 恢复 Cadence 工作，目标库为用户新建的 `project1`。当前采用用户确认的**本地制作 → 用户上传 Linux → 用户执行 → 回传结果**流程，不再自动操作远程桌面。

## 当前交付与下一步

- 第一包：[project1_probe_v1.0.0.zip](releases/project1_probe_v1.0.0.zip)，仅环境元数据检查。
- 用户操作：[开始这里](probe/开始这里.md)。上传、解压、终端检查、CIW 检查及回传均给出步骤。
- 本地验证：[local_validation.json](releases/local_validation.json)，8 项行为测试通过、Python/Shell 与 SKILL 静态结构检查通过。SKILL 实际执行、器件语义、许可证及电路仿真尚未验证。
- 第一版报告已收到且内部哈希一致；已确认 IC6.1.8、Spectre 21.1 和 project1 工艺关联。第一版漏收 Spectre CDF 与顶层模型入口，补查包为 releases/project1_probe_v1.1.0.zip。补查报告已收到，模型候选 sky130.lib.spice / tt 已发现；尚待器件名与 Spectre 兼容性实测。下一包为 releases/project1_m0_setup_v0.1.0.zip，先生成原生拓扑，按 m0_setup/操作说明.md 设置尺寸、导出网表和运行 DC。
- 第二包状态：**NMOS_DC_SMOKE_PASSED_REMAINING_M0_PENDING**。拿到报告后适配原生 schematic/symbol、Spectre/OCEAN、混合信号和物理验证，不猜测学校 PDK 参数或工具能力。
- M0–M5 均未在 Cadence 运行。此处文件打包完成不是芯片或仿真验收完成。

## 收到报告后的接续方式

1. 校验报告 ZIP 的哈希及运行编号；区分终端 PATH 和 Virtuoso PATH，核对 `project1` 与关联工艺。
2. 建立标准/低阈值 MOS、MIM、电阻、模拟测试源的 cell/端口/CDF 映射。合法尺寸与 multiplier 语义若仅有默认值，必须由 M0 实际最小电路验证。
3. 对标准单元 `sky130_fd_sc_hd`、混合信号、真实动态噪声及 DRC/LVS/PEX 分别记录“发现路径”和“实际运行通过”，不合并为一个环境 PASS。
4. 冻结当时选定的同版设计源与证据再制作第二包；旧 OTA 使用已有基准，新前端以 `v2/analog/frontend/dynamic_20260911/qualification.json` 指定候选及其哈希为本次计划基线，后续变更不得无声替换。ADC、数字宏、采样开关和已布线 CDAC 逐项核对依赖。
5. 用户先执行 M0/M1 并回传，再推进前端/ADC验证和物理闭合。完整前端正式多环路稳定性尚未闭合；已有开源 CDAC 物理 PASS 不等于 Cadence 或完整 ADC PASS。

## 当前证据

- 已在学校远程桌面看到 Virtuoso 6.1.8、Library Manager。
- CIW 日志确认 `project1` 成功关联 `sky130_fd_pr_main`。
- 当前学校 PDK 引用 `/project/engineering/cadence21/CDK/sky130_release_0.0.3/cds.lib`。
- 终端的 `cds.lib` 中，project1 路径为 `/home/compute/l.hongyi/cadence_skywater/project1`。
- 尚未核验 Spectre 模型、许可证、仿真运行或结果。尚未在 project1 创建 cell。
- 远程连接曾出现空白；重新加载后 noVNC 报告 `New connection has been rejected with reason: Authentication failed`。这是历史连接记录；用户已选择自行操作、上传和回传，当前不再尝试远程控制。

## 验证顺序

1. `tb_nmos_dc`：标准阈值 1.8 V NMOS，W=5 µm、L=0.5 µm；源极及体端接地，VDS=0.9 V，VGS 从 0 扫至 1.8 V，步长 10 mV，TT、27°C。记录模型路径、模型 section、器件参数及单位、实际 Spectre 版本、运行日志、Id–VGS 曲线及工作点。原 ngspice 单管数据位于 `reference/nfet_characterization_l0p5.tsv`。
2. 按原两级 OTA 建立原生 schematic 和 symbol，核对实例、尺寸、端口顺序、体端连接及补偿网络。M3、M4 各为两个显式并联单元；不能忽略或重复计算 multiplicity。
3. 在 TT/1.8 V/27°C、VCM=0.9 V、IREF=10 µA、5 pF ∥ 100 kΩ 到 VSS 的条件下，运行静态工作点、增益、环路稳定性与瞬态测试；与冻结的 ngspice 数据对照。原脉冲为 0.8→1.2 V、延迟 1 µs、上升/下降 20 ns、脉宽 2 µs、周期 5 µs。不同仿真器的 STB 与旧环路断开法须注明测量方法差异。
4. 环境和 OTA 对照通过后，再迁移同版前端与 ADC 候选。候选的实际性能验证完成后，按项目门槛推进完整版图、DRC、LVS、寄生提取及后仿真。

## 基准与结果区分

`reference/` 是已有本地 ngspice 证据的逐字节副本，不是新 Cadence 结果。
`reference_manifest.json` 保存原路径、SHA-256、标称参考值与单管条件；`cadence_measurements` 为 null，表示尚未运行。

Day 4 原网表的端口顺序为 `VDD VSS VINP VINN VOUT VBP`；展示用 core 网表的端口顺序为 `VINP VINN VOUT VDD VSS IREF`。迁移必须明确采用哪个接口，不能交叉套用。

学校 PDK 与原 ngspice PDK 的模型等价性尚未确认。旧前端、ADC 的已知失败仍保留，不能用 Cadence 连接成功代替电路验收。

## 2026-09-11 首次 NMOS DC 实测

用户回传的 Spectre 21.1 日志正常结束：0错误、1条 checklimitdest=psf 弃用警告，dc-0 至 dc-180 共181个工作点记录完整，27°C，VGS 0→1.8 V，最大漏电流1.129 mA。证据：reports/m0_nmos_20260911_152640/qualification.json。本次模型加载、求解及许可证通过；原始波形数值审计尚未完成。仅 NMOS DC 冒烟测试通过，完整M0及M1–M5仍未验收。以上早期“未运行”描述保留为历史状态，以本节为最新 NMOS 状态。

## PMOS 交付

releases/project1_pmos_dc_v0.1.0.zip 已生成：独立 tb_pmos_dc，源/体1.8V、漏0.9V、栅1.8-VSG。用户通过CDF表单设置5u/0.5u/一指/倍乘1后，按m0_pmos/操作说明.md导出网表并运行。局部几何、静态结构及包哈希检查通过，PMOS实际运行未执行。

## 2026-09-11 PMOS DC 实测

reports/m0_pmos_20260911_162236/qualification.json：Spectre正常结束，0错误、1条checklimitdest弃用警告、181个工作点。截图/M0/D末端约-211µA；日志最大电流记录是I(VS:p)=210.8µA，不能当作直接导出的漏电流数值。NMOS和PMOS DC基本流程均已跑通；原始波形数值审计、无源器件、统计及物理资格测试仍待完成。

## 2026-09-11 基础设计整包

`releases/project1_basic_design_v1.0.0.zip`：一次上传，生成 13 个原生 cell 和旧 OTA symbol，提供 87 个串行任务。包括工艺电阻/MIM/RC 测试、旧 OTA 工作点/AC/环路/阶跃、原有 13 点 PVT 与补充测试。入口和完整中文说明在 `basic_design/开始这里.md`。

原 OTA 保留理想 2 kΩ/3 pF 补偿与外部 10 µA 参考，不混用工艺无源替换后的结果。网表从原生 schematic 导出后检查；每个尝试独立保存，保留旧失败与缺失结果。原有 52 份 PVT 原始证据冻结到包内。本地行为测试以及原 13 点环路/瞬态测量回放通过，详见 `basic_design/local_validation.json`。这些是分析与文件包检查，**本包 SKILL/OCEAN 和新电路仍未在学校 Linux 执行**；学校 Python 3.6.8、CDF 回调、OCEAN 路径及输出信号名称的实际行为需现场验证。完整 M0/M1 不因交包而标成完成。

## 基础包 v1.0.1：PAS 初始化修订（最新）

用户实际运行 v1.0.0 在 M8 fingers 回调报 `PasCdfCommitValue: failed to find valid initialization data!`，生成中断，尚未开始仿真。v1.0.1 在参数回调前调用实例 CDF 的 formInitProc，并记录初始化过程。新 OTA 使用 `p1b_ota_legacy_r1`，测试台同步引用，保留旧中断 cell；不执行删除或覆盖。新上传包 `releases/project1_basic_design_v1.0.1.zip`，独立目录 `project1_handoff/basic_design_v1_0_1`。13 项本地测试、脚本词法及解压依赖检查通过，修订的学校 Cadence 运行仍待用户验证。具体操作见 `basic_design/本次修复.md`。

## 基础包 v1.0.2：类型判断修订（当前最新）

v1.0.1 实际执行报 `eval: undefined function - flonump`，在 CDF 参数写回阶段中断；该错误表明执行越过了初始化/回调代码，但不等于器件或整体生成通过。v1.0.2 使用 `type()` 的 string/fixnum/flonum 判断，并在任何 cell 创建之前运行五类值的 SKILL 类型自检。新 OTA 为 `p1b_ota_legacy_r2`，保留前两个中断版本。上传包 `releases/project1_basic_design_v1.0.2.zip`，独立目录 `project1_handoff/basic_design_v1_0_2`；14 项本地测试和解压检查通过，现场运行仍待验证。历史 ZIP 保留，不覆盖已交付版本。

## 基础包 v1.0.3：依据 M8 诊断冻结适配尺寸（当前最新）

v1.0.2 在 M8/w 严格核对中断，之后用户读到空 schematic。独立诊断结果归档于 `reports/m8_cdf_diagnostic_20260912`：PasCdfFormInit 成功，fw 回调把 w/fw 从 7.22005u 改为 7.22u，L=.8u、fingers=m=1 正确，扩散几何更新，诊断及保存完成。只验证了该 PMOS CDF 行为，不是仿真通过，也不足以推导全 PDK 的尺寸网格。

v1.0.3 明确选择 0.01 µm 精度的迁移宽度（逐管映射见 `basic_design/尺寸映射.md`），原源码/历史证据保留；最大相对宽度改变 <0.05%，性能影响仍须实际仿真。尺寸核对容差不放宽。新 OTA 为 `p1b_ota_legacy_r3`，保存逐实例现场，在尺寸检查前记录请求与实际值。15 项本地测试和打包检查通过；新包 `releases/project1_basic_design_v1.0.3.zip`、目录 `project1_handoff/basic_design_v1_0_3`，等待用户在学校执行。

## 基础包 v1.0.4：M7 并联拆分（当前最新）

用户实际运行 v1.0.3 报 M7 单指宽度72.2u超过学校上限50u并被截断，严格核对停止；原始报错归档 `reports/m7_width_limit_20260912`。v1.0.4 将 M7 拆成 M7A/M7B，各36.1u/.8u、一指、m=1，D/G/S/B逐端同网，总宽度72.2u。全OTA共13个MOS；工作点分别读取、组内汇总 ids/gm/gds，饱和裕量仍逐管检查。扩散寄生不宣称与单实例完全等价，需实际仿真对照。17项本地测试、87项入口词法及解压依赖检查通过，新OTA为 `p1b_ota_legacy_r4`；上传包 `releases/project1_basic_design_v1.0.4.zip` 和目录 `project1_handoff/basic_design_v1_0_4`，现场运行待验证。旧cell和发布包均保留。

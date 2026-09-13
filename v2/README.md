# SKY130 可校准传感器读出核心 — V2

**2026-09-13 更新：** 学校 Cadence 工作已恢复，本地同时新增旧 OTA 32 项对应表征、同源前端稳定性/噪声诊断、ADC 12 帧真实连续转换、真实宏装配 GDS 和学校新包放行检查。[本轮成果与真实未完成项](docs/local_preparation_20260913.md)。

状态：已从行为模型推进到真实 SKY130 晶体管电路、SAR 数字控制物理实现，以及前端＋ADC＋原始 RTL 的短时闭环转换。完整芯片尚未完成，不能把子模块通过拼成系统通过。新版正式稳定性、采样噪声、全码/长记录、完整核心版图和顶层寄生验收仍未完成；本轮没有发布新前端学校上传包。

旧版 OTA、结果与 Git 历史保持不变。所有新版文件位于本目录。

2026-09-10 更新：[本轮实际交付与剩余障碍](docs/non_cadence_20260910.md)。新增前端修复候选、真实 ADC 可恢复静态验证、噪声工具资格和原始证据完整性检查。没有把“不需要 Cadence”误写成“已全部完成”。

## 已落实的内容

以下区分“工具／代码完成”和“电路性能通过”，不是一张全部打勾的芯片验收表。

- 在模型／数字接口中实现三档增益 1/4/16、12-bit 偏移二进制输出、100 kS/s；不是完整模拟性能放行。
- 真正逐位决策的 SAR 行为模型，不是用一个理想量化器冒充所有 ADC 行为。
- 有限开环增益、失调、三次非线性、采样建立记忆、每次采样噪声和每次比较噪声。
- 二进制 CDAC 权重及 dummy 电容的合成误差敏感性分析；不是 SKY130 工艺 Monte Carlo。
- 标称三点校准，独立输入点验证，固定系数后保留漂移失败；不隐藏裁剪或重新标定。
- 相干 FFT、SNDR/ENOB/SFDR/SNR/THD、端点法 INL/DNL，以及独立的端码可达检查。
- 真实可编译的 SAR 控制 RTL；4 个完整采集周期加 12 个决策周期，连续请求无空闲周期。
- 故意加入高噪声、慢建立、电容权重错误和失调漂移，检查验收框架能否发现失败。
- 开源 PDK 器件资格：45 个工艺温压单管测试、200 个真实失配实例与种子控制；MIM 的 `m` / `mult` 统计缩放另有正反对照。
- 真实前端候选：全差分两级 PGA、CMFB、带启动偏置、PDK 电阻／电容／增益开关。已有标称噪声和动态建立进展，但首版固定校准跨温压失败；高输入阻抗改进候选单独保留。
- 真实 ADC 候选：二进制 MIM CDAC、采样／参考开关、StrongARM 比较器及保持锁存；底板采样＋前置隔离放大候选用于降低寄生影响和回踢。
- 数字控制完成标准单元综合、布局布线、DRC/LVS、寄生提取、九角静态时序及布线后网表全码功能回归；这是数字宏，不是完整芯片版图。
- 四 MOS 采样开关完成独立版图 DRC/LVS、R/C 提取；原理图／RC 的 2430 个有限条件点通过。实际输入／共模／源阻抗与工艺温压范围见报告，仍不包括完整 ADC、失配和随机噪声。
- R/MIM/CMOS 采样相位生成器通过全部 45 个独立工艺温压时序测试，最短实测采集窗口约 2.47685 µs；采样电路必须在该真实窗口内建立。
- 原始 SAR RTL 和真实 ADC 已闭环连续转换；旧前端 16 倍也已接入完成短时转换。此证据没有包括完整码域、随机器件噪声或顶层寄生。
- 外部数据导入、固定系数拟合／应用／独立验证工具保留原始码，检查样本数、裁剪、重用训练点和跨温压偷偷重拟合。

## 运行

需要 Python 3.12、requirements.txt 中的 NumPy，以及 Icarus Verilog / vvp。没有数字仿真器时，整套验证会明确报未完成，不会跳过后仍返回通过。

在仓库根目录执行：

    python3 v2/scripts/run_validation.py

只运行系统实验：

    python3 v2/scripts/run_behavioral.py

只运行数字逻辑测试：

    python3 v2/tests/rtl/run.py

这些离线命令不连接学校服务器、不启动 Cadence、不下载 PDK，也不修改旧版项目。真实电路／物理实现的独立入口见 [开源环境](environment/README.md)、[数字物理实现](physical/digital/README.md) 和 [混合仿真](integration/README.md)。

## 从这里查看结果

- [实验报告](results/behavioral_report.md)：模型条件、校准前后与失败检测。
- [模型与代码验证](results/validation.json)：测试输出、代码指纹和旧版保护检查；只对该报告列出的测试有效，不代表模拟电路终验。
- [整个项目是什么芯片](docs/chip_overview_zh.md)：面向初学者的功能、输入输出、外部依赖与完成边界。
- [全项目证据索引](results/project_evidence.json)：逐项范围、来源哈希、失败和未完成项，不生成虚假的“全芯片通过”。
- [冻结前端候选的失败审计](analog/frontend/results/frozen_delivery.json)：同一版本的直流、噪声、采样、共模振荡与固定校准结果。
- [新前端修复实验](analog/frontend/repair_20260910/README.md)：按同一电路版本分组，保留改善、失败和数值未完成。
- [真实 ADC 全码验证框架与吞吐实测](analog/adc/verification_20260910/README.md)：全码任务尚未跑完，六次短转换不能代替全码成绩。
- [随机噪声工具资格](verification/noise_20260910/README.md)：RC 噪声正常不代表 SKY130 噪声模型匹配。
- [器件资格](environment/results/device_qualification.json)、[MIM 统计缩放资格](environment/results/cap_multiplier_qualification.json)、[小版图闭环](environment/results/physical_qualification.json)。
- [数字控制版图与寄生验证](physical/digital/results/physical_validation.json)。
- [独立采样开关的 2430 点原理图／RC 回归](physical/adc_switch/results/dummy_w4w8_rc_full.json)。
- [真实相位电路 45 点时序](integration/results/phase_qualification.json)。
- [数字逻辑验证](results/rtl_validation.json)：全码、复位、连续转换等测试。
- [冻结规格](config/spec.json)：设计目标与假设模型参数分开放置。
- [误差预算](results/error_budget.json)：单位、时序、噪声分配和候选电容规模。
- [未执行的工艺角矩阵](results/qualification_matrix.csv)：45 个工艺/温压组合乘三档增益，135 行均为 NOT_RUN。
- [阶段状态与后续任务](docs/status.md)、[接口说明](docs/interfaces.md)、[数字时序细节](docs/digital_control.md)。

## 不能把这些结果解读为什么

配置中的 86 dB 开环增益、5 µV 输入噪声、180 ns 时间常数等是预算假设，没有由 SKY130 电路提取得到。
模型输出的 SNDR/ENOB 只能说明这些假设在数学上如何组合；不能写成简历中的实际芯片性能。

原 Python 行为模型尚未充分刻画源阻抗加载、连续噪声折叠、参考端压降、CMFB、比较器回踢及 MOS 注入。新增解析预算与真实 PDK 电路已分别检查其中一些因素；其范围以各报告为准，不追溯性地把原模型数字升级成实际电路成绩。

线性校准只能消除静态增益和失调；归一化 SNDR 基本不变。校准后平均残差很小不代表单次转换获得 12-bit 有效精度。
已经存在器件／部分模块的 200 个真实失配样本、45 点 PVT、功耗和版图证据；完整前端＋ADC 核心的 200 样本、135 个系统组合、完整面积、顶层寄生和噪声包含的 SNDR 仍未完成。

## 复现与依赖边界

behavioral_manifest.json 保存模型/config/脚本及每个结果文件的 SHA-256。
validation.json 保存包含测试与 RTL 的源码指纹；运行前先置为 RUNNING，中途失败不得使用上次结果声称本次通过。
运行前后会比较模型、配置、测试及 RTL 的指纹；运行期间发生变更则拒绝通过。验收门限和固定时序不能通过只修改配置文件降低。
源代码和配置变化后必须重新运行验证。旧文件可以保留作历史数据，但需对照指纹与权威状态。

只保存自有代码、公开依赖版本和分析结果。不提交学校账号、许可证或受限 PDK，即使仓库是私有的也不例外。

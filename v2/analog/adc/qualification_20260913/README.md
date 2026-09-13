# ADC 本地电路级推进报告（2026-09-13）

**12 帧功能一致，但数值波形未收敛，不能认定可靠连续转换已验收。** 两组同一物理 CDAC 差分节点的最大差为 **48.393 mV**（联合接受时间点格）；在公共 **1 ns** 时间格上仍为 **4.077 mV**，均远超 **0.05 LSB = 9.765625 µV** 门限。

本轮覆盖正负近满量程、零点两侧、多个新码中心和大幅交替跳变。完整 ADC 验收仍未完成；全码、长记录频谱和完整 ADC 失配均未冒充通过。

| 配置 | 实际耗时 | 结果 | 完整转换 / 真实判决 |
|---|---:|---|---:|
| baseline | 393.553 s | CONTINUOUS_12_FRAME_FUNCTIONAL_PASS | 12 / 144 |
| strict | 839.944 s | CONTINUOUS_12_FRAME_FUNCTIONAL_PASS | 12 / 144 |

每次完整运行均为 122 µs、100 kS/s；只复位一次，全部 12 帧均保留。TT、1.8 V、27 °C、350 Ω/端、参考源 1 Ω + 10 nF。真实 SKY130 CDAC、开关、前放、动态比较器及 SAR RTL 均保留，使用已修复 33 位输出掩码的本地桥。

输出码由实际总线、RTL 日志、144 个 Q/QB 判决窗口互相核验；50 个 ready/busy 状态点独立检查。理想码仅作诊断，不决定真实比较器结果。每次仿真原始网表、波形、日志、退出码和哈希均在 results/ 对应目录。

数值对照状态：**NUMERICAL_CONVERGENCE_FAIL**。baseline 使用 2 ns 最大步长及 reltol=1e-5；strict 使用 1 ns 最大步长，并将 reltol/abstol/vntol 全部收紧十倍。

CDAC 差分误差：接受点联合时间格最大 48393.343798 µV（247.773920 LSB）；公共 1 ns 格最大 4076.773191 µV；全部判决前检查点最大 0.013376 µV。严格门限保持 0.05 LSB = 9.765625 µV。小的判决前误差和相同输出码不能覆盖全波形失败。

按本轮最慢完成配置外推，131073 次无预热连续转换约 106.19 天；当前 batch=8、预热与前一点回放方案约 225.65 天；16384 点加 256 次预热的一条连续记录约 13.48 天。这只是一次实测的线性资源估计，不是运行承诺，也不是全 PVT 预算。

全码计划固定为 4096 × 32 + 1 = **131073 点**，当前完成 **0 点**。campaign.py 的 run 入口实测退出 2，保持质量门关闭；计划与单 worker、保留失败、显式重试、每次最多一批的底层恢复协议已保留。此版本不开放长跑，新的数值资格必须另立可审计版本，不能修改已有失败结果。

campaigns/spectrum_and_mismatch.json 固定了 **16384 点**、bin=7373、45001.220703125 Hz、−1 dBFS 的连续正弦记录约束，以及 **200 个完整 ADC 独立失配样本**要求。它们是未执行的约束描述。确定性 FFT 不作为含器件噪声 SNDR；独立复位的短记录不能拼成连续频谱。旧 CDAC 和比较器分别 200 例的统计结果均不是完整 ADC 失配样本。

现有真实 CDAC PEX 的全 4096 码静态线性仍有单调性失败；它是后续完整 ADC 后仿的依赖项，本目录未修改其版图或结论。

## 复现与学校迁移边界

唯一已验证运行环境是现有本地 Linux AArch64 容器及其冻结的 ngspice/PDK。桥二进制 ELF e_machine=183（ARM64），不能直接作为 x86_64 学校 Linux 可执行文件。run_checked.py 会明确拒绝错误架构，并核验实际加载的助手文件、RTL、电路和桥哈希。PDK 与工具身份由运行器再次检查。support/ 中的补充助手审计与原有冻结源码逐字节一致；该补充审计记录在 baseline 运行之后。

在现有容器 /repo 下执行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py check
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py baseline
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py strict
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/campaign.py collect
```

前两类真实实验每次保存新的独立结果目录，单次最多 900 s；collect 当前应退出 2 并报告 0/131073。学校迁移还需对应架构重建桥、实际学校模型及许可、Spectre 语法/模型验证，以及先完成短握手与转换资格；本目录没有未经学校验证的 Spectre 批量任务。

## 证据入口

- report.json：全部实际运行、数值结果、预算、历史证据边界、ABI 与验证退出码。
- snapshot/manifest.json、support/manifest.json：电路、RTL、已修复桥、PDK/工具记录与分析助手源哈希。
- numerical_comparison.json：联合接受点时间格及公共 1 ns 时间格的严格数值比较。
- peak_diagnosis/：最大误差附近两组原始时间轴、同一物理 TP/TN 节点电压、数字/真实相位边沿位置；尚未隔离造成该误差的具体机制。
- results/*/conversion_table.csv：逐帧输入、真实输出码、比较器字及 valid 时间。
- validation/：软件负面测试、质量门关闭、全码零覆盖、源/架构检查的实际输出。这些软件测试不是新增电路样本。
- solver_probe/：单独的 KLU 工作点能力诊断；不将工作点完成算成瞬态速度或数值资格。选项依据见 [ngspice 官方说明](https://ngspice.sourceforge.io/applic.html)。

未完成项仍是：完整全码 INL/DNL、含器件噪声的长记录频谱、200 例完整 ADC 失配、完整 PVT、整个 ADC 寄生后验收以及学校 Cadence 资格。

# 学校 Cadence 最小迁移核对

本目录提供已在本地运行的电路和数值基准，**没有提供未经学校验证的新 launcher 或批量原理图生成包**。学校操作继续使用现有已经跑通的 `basic_design_v1_0_4 + 1.0.4p3` 环境；不重新执行旧版出错初始化、不猜 PATH、不覆盖 project1 的已有 cell。

已记录的环境边界：

| 项目 | 本地实际使用 | 学校既有记录 |
|---|---|---|
| 求解器 | ngspice 47 | Spectre 21.1 |
| 求解器路径 | `/foss/tools/ngspice/bin/ngspice` | `/project/engineering/cadence21/spectre/tools/bin/spectre` |
| 原生设计工具 | 未使用 | Virtuoso IC6.1.8 |
| 模型入口 | `/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice` | `/project/engineering/cadence21/CDK/sky130_release_0.0.3/models/sky130.lib.spice` |
| OCEAN | 未使用 | `/project/engineering/cadence21/ic/tools/dfII/bin/ocean` |
| 工作目录 | `/repo/v2/analog/frontend/qualification_20260913` | `/home/compute/l.hongyi/cadence_skywater` |

学校 OCEAN、Spectre、模型和工作目录均逐项来自最新现场报告 `cadence/project1/reports/basic_20260913T023544Z_5cc09eef/received/site.json`。其中工作目录是该报告的 `workdir`，不是上传包的子目录；OCEAN 实际路径包含 `tools/dfII/bin`，已替代早期说明中的旧路径。本轮没有重新运行学校环境。模型路径相似不证明模型版本、CDF 参数或无源尺寸等价。现有实际启动路径应由主任务引用当前已验证脚本，不从本地 `/foss` 推导。

## 首先逐项核对的接口与依赖

主入口 `sky130_v2_switchable_pga` 的引脚顺序固定为：

`VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1`

代码以 `(SEL1, SEL0)` 解释：00=G1，01=G4，10=G16，11 保留且反馈断开。首个试验固定 G4：SEL0=1.8 V、SEL1=0。不要把旧 OTA 引脚顺序套入，也不要采用 sample_driver 默认 1.8 kΩ；已测装配是 PGA 外接每侧 1.5 kΩ 与 4 pF。

必须在学校原生导出网表核对以下内容，再运行最小试验：

- 标准 NMOS/PMOS及采样开关所需 LVT MOS 的真实 cell/model、四端顺序和体端；W/L、finger、m 的乘数关系，防止重复乘倍。
- 高阻多晶硅 0.35 µm 和 0.69 µm 宽度版本的合法 CDF 字段及模型映射。特别是 1.2 kΩ Miller 调零采用 0.69 µm 器件，L≈0.855177 µm；1.5 kΩ 隔离采用 0.35 µm，L≈0.542800 µm。旧默认电阻 M0 通过不能证明这些特定尺寸已通过。
- MIM W/L 与并联单元语义；4 pF 滤波、8 pF Miller 与每侧 4096 单元真实采样阵列，不得把 COUNT 当作忽略的注释或再次乘倍。
- `VCM` 确实接入 `XCMR` 栅极；NCM/CMS/CMG 的感测和调节连接；两边交叉反馈及六条开关支路。
- 模型 section TT、1.8 V、27°C；输入每端 350 Ω，采样开关固定导通。测试用理想刺激可以使用，但内部放大器、R/C 和开关不可用行为块替代。

## 已跑通的小型基准

本地结果：`runs/20260913T062412790986Z_noise_g4_acquire/`。其中 `bench.spice` 是真实运行网表，`candidate_06.spice`、`sampling_switch.spice`、`adc_blocks.spice` 是依赖快照，`op.dat`、`ac.dat`、`dc.dat` 与日志齐全。目录名保留调用器生成的 `noise`，其真实状态是 `LOCAL_G4_CANARY_COMPLETE`，未运行噪声分析。

试验只做 G4 工作点、1 kHz AC 和三个 DC 点。测试源令 VINP=0.9+SW/8、VINN=0.9−SW/8；SW 取 −0.32/0/+0.32 V，实际传感器差分输入为 SW/4。

| 项目 | 本地实测基准 |
|---|---:|
| 零输入输出共模 | 0.886288513 V |
| 1 kHz，输出差分/SW | 1.009873411 |
| 1 kHz，输出差分/传感器差分 | 4.039493645 |
| SW=−0.32 V 的输出差分 | −0.323151835 V |
| SW=0 的输出差分 | 约 −1.79 pV |
| SW=+0.32 V 的输出差分 | +0.323151835 V |

这些数值用于发现符号、倍乘、单位、端口和模型差异，没有将“与 ngspice 一致”的新百分比容差强加为最终验收门限。学校第一次只需原生导出网表和此最小试验的真实结果；若出现差异，先比较模型/CDF/装配与输出参考点，再决定是否可继续三档稳定性或 PVT。学校最小试验尚未执行，原生原理图迁移尚未完成。

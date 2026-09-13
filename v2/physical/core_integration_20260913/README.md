# 核心版图与顶层后仿真本地准备（2026-09-13）

已把现有三个真实宏的版图放入同一个可打开的 GDS，并完成源证据、端口和后提取视图的核对。**这是未布线的局部装配，不是完整核心版图；尚未进行顶层 LVS、PEX 或性能后仿真。**

本轮仅在本目录增加文件。没有改旧模块、既有通过/失败证据或学校 Cadence 工程。

## 已实际完成

| 产物或检查 | 本轮结果与边界 |
|---|---|
| 既有宏证据复核 | 148 项通过；检查冻结哈希、原始 DRC/LVS 日志、RC 元件、端口顺序和 8712 个 MIM |
| 真实宏装配 GDS | 1 个差分 CDAC、2 个四管采样开关、1 个数字控制宏；共 4 个顶层实例，无占位假模块 |
| KLayout 独立回读 | 实例数和互不重叠检查通过；输出实际引脚坐标和层号 |
| Magic 装配几何检查 | 从新 GDS 重新导入，原始输出 `Total DRC errors found: 0`；只适用于当前未布线装配 |
| 局部电气连接夹具 | 真实 CDAC RC + 两个真实四管开关 RC；显式保留所有底板端口和时钟/参考接口 |
| 顶层后仿真准备门控 | 正确返回 `BLOCKED_FULL_CORE_POSTLAYOUT`（退出码 2），不会将宏通过或几何 DRC=0当作芯片通过 |
| 防误判检查 | 7 项测试通过，覆盖旧哈希、未提取网表、交换 A/B、缺模块、基底绑定和 135 点矩阵 |

装配外框为 **1093.2 × 469.795 µm**。它只包含上述宏和暂定间距；未来模拟模块、参考和时钟布线均未计入，不能用它报告最终核心面积。

![真实宏局部装配，所有宏间连线尚未完成](reusable_macros_UNROUTED.png)

## 两个会影响后仿真正确性的发现

**CDAC 提取网表的 `VSUBS` 原本是内部节点，没有列入 30 个端口。** 直接在 SPICE 中实例化会留下局部基底节点，无法由外部 VSS 约束。本目录生成了 `cdac_diff_routed_substrate_bound.spice`：只更名子电路并追加 `VSUBS` 端口；所有电容、电阻和 MIM 实例行逐字保持。局部夹具将这个新端口接 VSS。原始提取文件保持不变；这只是明确基底边界的仿真适配，不是新一轮 PEX。

此外，旧 CDAC 汇总使用仅识别 `f` 后缀的正则表达式，记录了 17,710 个电容。独立复核发现原网表实际含 **17,732 个 C 项：17,730 个正值，2 个零值**；另有 20 个正值使用 `p` 后缀。所有 26,210 个 R 项及 8712 个 MIM 均保留。这里纠正计数说明，没有变更旧报告，也没有凭元件数推断精度。

**数字宏的 SPICE 是 LVS 拓扑视图，R=0、C=0，且有抽象空子电路。** 数字宏确实具有已验证的 SPEF、SDF、门级网表和 STA，但不能把该 SPICE 直接当成完整晶体管 RC 后仿真。绑定表已明确区分这些视图；最终需要完成合格的门级时序/模拟电平接口联仿，或另行生成完整晶体管 RC 提取。

采样开关的 A/B 有方向：本夹具把 A 接 `VCM_CLAMP`，B 接保持的 P/N 顶板。它没有声称旧独立输入采样测试已经覆盖真实底板切换或顶板钳位行为。开关原物理报告列出的 10 个中间文件未包含在可携带 artifacts 中；本报告列出它们，未把缺失中间文件当作哈希通过。现有最终 GDS、RC、MAG、LVS 报告与布局日志的哈希都已实际核对。

## 文件入口

- `macro_evidence_audit.json`：148 项证据检查、原始/正值 RC 计数、未保留中间文件清单。
- `reusable_macros_UNROUTED.gds`：真实局部装配；顶层名 `REUSABLE_MACROS_UNROUTED_20260913`。
- `assembly_readback.json`：实例、外框、引脚坐标、层号、无顶层连线状态。
- `assembly_drc.log` / `assembly_geometry_validation.json`：本轮 Magic 几何检查原始输出与哈希绑定。
- `extracted_view_bindings.json`：冻结 GDS/网表/SPEF/SDF、端口与哈希；缺失视图明确为空。
- `cdac_clamp_pex_partial.spice`：可供下一阶段构建 testbench 的局部子电路，**不是独立可运行仿真台**；需按项目环境加载公开 PDK 模型、外部参考、底板驱动、真实时钟和刺激。
- `postlayout_acceptance_matrix.json`：G1/G4/G16 × 5 工艺 × 3 电源 × 3 温度，135 个基础条件，全为 `NOT_RUN`。
- `postlayout_readiness.json`：明确的完整核心后仿真阻塞原因。

矩阵从 `v2/config/spec.json` 读取门限：100 kS/s，12 bit，0.8 Vpp，标称/角落 SNDR ≥65/62 dB，功耗 ≤2/3 mW，建立误差 ≤0.25 LSB，静态校准残差 ≤1/4 LSB，INL ≤1.5 LSB，DNL −0.9 至 +1.5 LSB，相位裕量 ≥60°。16,384 点频谱与至少 200 个系统失配样本单独保留要求。135 是基础 PVT 行数，不包含共模/源阻抗敏感性、多个频点、失配样本和校准采样的扩展量；没有把 200 样本擅自解释成每个 PVT 都要重复 200 次。

该门控只检查**可以开始完整后仿真的输入是否齐备**。即使未来返回 `READY_FOR_FULL_CORE_POSTLAYOUT_SIMULATION`，也不会给出芯片性能 PASS；还必须实际执行矩阵并审核原始波形、噪声方法、统计与完整周期功耗。

## 继续完成所需的最小输入

1. 同一版前端完成正式多环稳定性、噪声与 PVT 后冻结源码；目前已有动态候选，不能提前冻结版图签核。
2. 前端、比较器/前置放大、参考选择与分配、非重叠相位及实际驱动器的真实版图和对应原理图。现有物理目录没有这些宏。
3. 冻结参考的 tracking/fixed 合同，完成真实时钟负载和采样/钳位/底板接口的联合转换验收。
4. 按冻结接口连接所有宏、电源和基底，再跑**完整核心** DRC/LVS/PEX；宏级寄生不包含未来宏间走线的影响。
5. 将完整核心提取视图绑定回三档条件，完成连续转换、全码、长记录含噪声频谱、失配、建立和功耗验收。数字现有九角 STA 不能替代模拟 45 PVT。

本地开源工具已可继续实施这些步骤；无需为本次准备提供新账号或受限 PDK。迁入学校 Cadence 和按学校工艺规则签核属于后续独立闭环。

## 复现

从仓库根目录执行：

```sh
python3 v2/physical/core_integration_20260913/prepare.py
python3 v2/physical/core_integration_20260913/test_preparation.py
python3 v2/physical/core_integration_20260913/postlayout_gate.py
```

第三条当前应返回退出码 **2**，表示真实未满足的前置条件；不得用忽略退出码的方式称它通过。

物理装配与几何复核使用已有离线容器：

```sh
docker exec sky130-v2-resume-20260910 python3 /repo/v2/physical/core_integration_20260913/assemble_gds.py
docker exec sky130-v2-resume-20260910 bash -lc 'magic -dnull -noconsole -rcfile /foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc /repo/v2/physical/core_integration_20260913/check_assembly_drc.tcl > /repo/v2/physical/core_integration_20260913/assembly_drc.log 2>&1'
```

以上没有运行新的晶体管瞬态仿真，没有进行完整核心 LVS/PEX，也未操作 Cadence。

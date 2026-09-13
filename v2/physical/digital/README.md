# SAR 数字控制宏：开源版图与后提取验证

**状态：独立数字宏验证通过。不是整个 ADC，也不是整个读出芯片完成。**

使用已有 SKY130A PDK 和 LibreLane / Yosys / OpenROAD / Magic / KLayout /
Netgen 完成，没有使用 Cadence，没有制造芯片。

模拟比较器接口的实际接收负载与 setup/hold 抽象见
`results/interface_validation.json`，可用 `python3 v2/physical/digital/interface.py`
从保留的九角提取 Liberty 重建。最大接收电容 3.5 fF、最大 setup
3.06730 ns；模拟端使用 5 fF、捕获后保持 5 ns 的独立测试合同。
这些负载不包含未来顶层模拟走线的额外寄生。

## 实际结果

| 项目 | 结果 |
|---|---:|
| 宏矩形 | 150 × 150 µm，22,500 µm² |
| 标准单元面积，含时钟及修复单元 | 3,674.77 µm² |
| Magic DRC / KLayout DRC | 0 / 0 |
| Netgen LVS | Circuits match uniquely |
| 两种 GDS 生成路径 XOR 差异 | 0 |
| 天线、断连、最大电容／转换时间违规 | 0 |
| 后提取 STA | 3 个数字库角 × 3 个 RC 角，全部通过 |
| 最差 setup / hold 余量 | +7.857665 ns / +0.139204 ns |
| 最终布局网表的功能回归 | 687,790 项检查，覆盖所有 4096 个码 |
| 指定测试负载下的数字功耗估算 | TT 25°C 1.8 V 下约 8.123 µW |

功耗使用最终网表的零延迟门级活动、标准单元功耗模型与标称 SPEF；
1,028 个活动引脚全部有 VCD 标注。它不是最差工作负载、模拟电路功耗、
真实晶体管供电电流或硅测成绩。时序由 STA 单独检查，门级功能回归没有
使用 SDF 延迟，不能把两者混称为时序仿真。

详细、可机器核验的结论见 `results/physical_validation.json`；
每个工艺库／RC 角的余量、通过条件、输入和产物 SHA-256 均被记录。
测试覆盖保留在 `results/routed_gate_validation.json`。

## 使用与复现

在已准备的离线 EDA 容器中、仓库根目录执行：

```sh
SAR_PHYSICAL_RUN_TAG=final bash v2/physical/digital/run.sh
python3 v2/physical/digital/verify_routed.py final
python3 v2/physical/digital/summarize.py final
```

已存在的 run 不会自动覆盖。重新实现时选一个新的 run tag，并在后两条
命令中使用相同 tag。完整中间数据保留于本地 `runs/`，不加入 Git；
可移植产物位于 `artifacts/`，关键报告与冻结源快照位于 `evidence/`。

`artifacts/` 含 GDS、LEF、DEF、ODB、SPEF、宏 Liberty、SDF、Verilog 网表、
SPICE 提取网表和真实版图渲染图。它们仅描述本数字宏。

## 设计边界与已解释的失败

- 时钟 625 ns，输出驱动条件为每端 50 fF；比较器输出须在下降沿后
  250 ns 内稳定，并保持到下一上升沿之后。实际模拟负载必须继续核验。
- `comparator_evaluate` 是模拟相位控制输出，不是同步数据接收端。
  保留 10 ns 时钟到输出的传播上限，但不施加不适用的同步 hold 检查。
  模拟非重叠时钟、窄脉冲及比较器保持仍需在顶层验证。
- 异步复位释放须由上层同步；任意时刻释放的 recovery/removal 未获证明。
- 初始 run 的相位输出约束把 100 ns 外部延迟重复计入 10 ns 传播上限，
  因此失败；后续 run 又暴露了相位输出不适用的同步 hold 约束。
  两次诊断没有改 RTL，也没有豁免真实寄存器的 hold；最终 run 全量重跑。
- 初始最差角有约 1.4 fF 最大电容超限，增加真实物理修复余量后消除。
- 原始 Yosys 面积映射存在真实 pre-layout hold 失败，最终通过时钟树与
  延迟单元修复。`v2/digital/results` 保留该基线，不伪装成原本已通过。
- 9 个数字库与 RC 角不是模拟项目要求的 45 个工艺／温压组合。
- 开源规则检查通过不等于晶圆厂生产签核；本项目不包含焊盘或流片。

第三方标准单元的归属与使用条件见 `THIRD_PARTY_NOTICE.md`。

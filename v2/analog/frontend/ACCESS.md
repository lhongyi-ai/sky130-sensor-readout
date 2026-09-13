# 如何访问模拟前端

这里的“前端”是芯片中连接压力传感器与 SAR ADC 的**模拟前端电路**，不是网页前端，因此没有网址、登录页面或可以点击操作的 Web UI。

当前权威电路是 [`dynamic_20260911/candidate_06.spice`](dynamic_20260911/candidate_06.spice)。它使用 SKY130 器件，提供 1、4、16 倍三档增益，并驱动真实 4096 个 MIM 单元／侧的 SAR 采样负载。它在标称条件下通过三档静态与动态检查，但正式多环稳定性、45-PVT、噪声和前端物理版图尚未闭合；因此不能称为最终合格前端。

## 方式一：直接看图，不安装软件

进入 [`xschem_20260911/renders`](xschem_20260911/renders) 后依次打开：

1. [`frontend_top.png`](xschem_20260911/renders/frontend_top.png)：整个信号链，从差分传感器到 PGA、RC 隔离和 SAR 采样器。
2. [`switchable_pga.png`](xschem_20260911/renders/switchable_pga.png)：1、4、16 倍增益如何通过反馈电阻和开关选择。
3. [`rd_fdota.png`](xschem_20260911/renders/rd_fdota.png)：两级全差分 OTA 的晶体管、偏置、补偿和两个共模控制回路。

三张图均为 2400×1600，已经逐张检查文字、器件、导线和边框之间的间距。也提供同名 SVG，放大后文字和线条仍然清晰。

## 方式二：用 Xschem 打开并缩放查看

Xschem 是开源原理图工具。安装并进入下面的目录：

`/Users/stanley/Documents/ChatGPT/Analog Circuit Project/sky130-two-stage-ota/v2/analog/frontend/xschem_20260911`

然后分别打开：

```sh
xschem frontend_top.sch
xschem sky130_v2_switchable_pga.sch
xschem rd_fdota.sch
```

项目容器 `sky130-v2-resume-20260910` 中已经配置 Xschem 3.4.8RC 和 SKY130 环境。如果只需要重新导出图片，可在容器里进入 `/repo/v2/analog/frontend/xschem_20260911` 后运行：

```sh
./render_headless.sh
```

这些 `.sch` 文件是便于阅读的分层审阅图，不是 Cadence Virtuoso 原生原理图，也不应从中重新生成网表来替代权威 SPICE 电路。

## 方式三：查看真正用于仿真的电路

打开 [`dynamic_20260911/candidate_06.spice`](dynamic_20260911/candidate_06.spice)。关键层次如下：

| 行附近 | 子电路 | 作用 |
|---:|---|---|
| 63 | `rd_bias` | 片内偏置与启动 |
| 73 | `rd_fdota` | 两级全差分 OTA、补偿和共模控制 |
| 125 | `rd_fbbranch` | 一条真实电阻＋传输门反馈支路 |
| 132 | `sky130_v2_switchable_pga` | 1／4／16 倍增益选择与交叉反馈 |
| 156 | `sky130_v2_switchable_sample_driver` | 输出隔离与 ADC 采样驱动 |

网表中的 `X...` 表示器件或子电路实例；MOS 管的 `W`、`L` 是宽度和长度。这里的晶体管、电阻和 MIM 电容均引用可布局的 SKY130 PDK 器件，不是理想运算放大器方块。

## 证据与当前边界

- 最新结论：[`dynamic_20260911/qualification.json`](dynamic_20260911/qualification.json)
- 前端实验说明：[`dynamic_20260911/README.md`](dynamic_20260911/README.md)
- Xschem 图纸说明：[`xschem_20260911/README.md`](xschem_20260911/README.md)
- 图纸完整性与来源哈希：[`xschem_20260911/artifact_manifest.json`](xschem_20260911/artifact_manifest.json)

当前准确状态是：**非 Cadence 前端电路、可读原理图和标称三档动态验证已经可以访问；Cadence 原生原理图、正式多环稳定性、45-PVT、噪声、前端版图、DRC/LVS/PEX 与后仿真仍未完成。**

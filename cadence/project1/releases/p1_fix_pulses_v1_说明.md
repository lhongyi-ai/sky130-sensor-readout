# 脉冲源参数修复 v1

这次报告中 OCEAN 正常生成网表，网表器报告 0 errors / 0 warnings。但 RC 的 `VIN` 被导出为 `type=pulse val0=0 val1=0`，没有期望的电平和时间设置，严格参数检查在仿真前拦截了它。

原因是基础包生成器把 Spectre 的输出参数名直接写入了 `analogLib/vpulse` 实例。正确映射为：

| 原理图 CDF 属性 | Spectre 输出参数 | RC 输入 VIN | OTA 阶跃输入 VINP |
|---|---|---:|---:|
| v1 | val0 | 0 | 0.8 |
| v2 | val1 | 0.1 | 1.2 |
| td | delay | 1n | 1u |
| tr | rise | 1p | 20n |
| tf | fall | 1p | 20n |
| pw | width | 5n | 2u |
| per | period | 10n | 5u |

学校第一份检查报告已记录 analogLib/vsource 的这七个名称；[Cadence 官方关于 vpulse 属性的说明](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/18773/may-i-use-some-skill-function-to-edit-a-component-cdf-in-my-current-design)也明确使用 `v1`。脚本仍会先检查学校实际 `vpulse` CDF 中七个参数全部存在，再进行修改；缺少字段或出现冲突值时停止。

## MIM 命令需要在同一行

这次 MIM 没有运行：启动器被单独执行，没有带参数；随后 `run --job ...` 被当成另一个 Linux 命令。

在 Linux 终端完整复制下面的一行，`.sh` 后不要按回车：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job mim_ac --retry
```

## 修复两个已生成的脉冲源

1. 将 `p1_fix_pulses_v1.il` 上传到 `/home/compute/l.hongyi/cadence_skywater/`。这是单个 SKILL 文件，无需解压。
2. 若 `p1b_tb_rc` 或 `p1b_tb_step` 的原理图窗口开着，先保存并关闭这两个编辑窗口。保持 Virtuoso 主窗口 CIW 开着。
3. 在 **Cadence CIW 底部输入栏**执行下面一行，不是在 Linux 终端执行：

```lisp
load("/home/compute/l.hongyi/cadence_skywater/p1_fix_pulses_v1.il")
```

预期出现两个 `P1_PULSE_SOURCE_SAVED`，最后出现：

```text
P1_PULSE_REPAIR_DONE: 2 sources saved. Next rerun native audits; NOT A SIMULATION PASS.
```

脚本只修改 `project1/p1b_tb_rc/VIN` 和 `project1/p1b_tb_step/VINP` 的七个正确 CDF 属性。两处都会先核对本包的所有权标记、vpulse master、旧刺激值和真实 CDF 字段，再修改。保留旧属性及修改前后的读回日志，不触碰 MOS、工艺 R/C、接线或库定义，不执行 MOS/PAS 回调，不重新建立电路。

读回、检查及保存结束不代表仿真通过；仍由后续原生网表核对验证全部电平和时间参数。若脚本报错，请回传 CIW 全文及 `basic_design_v1_0_4/runs/p1_pulse_repair_v1.log`，先不要重跑或删除 cell。

## 重新运行 RC 并回传

看到修复完成标志后，回到 **Linux 终端**，执行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job rc_step --retry
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

回传新的报告 ZIP。修复日志位于 runs/ 下，会自动进入结果包。预期新原生 RC 网表中，VIN 有 `val0=0 val1=0.1 delay=1n rise=1p fall=1p width=5n period=10n`，字段顺序可不同。原错误网表和失败状态不修改。

电阻旧 CDF 阈值已经被模型复核证明不适用；RC 原时间常数门槛也仍待结合实际 MIM 和工艺寄生确认。此文件不放宽这些门槛，不宣布尚未完成的被动件或 OTA 仿真通过。

本地验证包括 SKILL 括号／字符串检查、全部两个脉冲源及 14 个值与冻结设计一致、报告中的错误网表确实被拒绝，以及正确电平／时间网表的检查器回归。SKILL 实际执行仍待学校 Cadence 验证。

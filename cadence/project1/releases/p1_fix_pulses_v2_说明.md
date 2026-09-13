# 脉冲源修复 v2：解决属性查询函数错误

v1 的 `dbFindPropByName` 在学校 Virtuoso 中不存在。错误发生在第一次只读预检查内，尚未进入修改或保存脉冲参数的阶段。这是修复脚本的错误。

v2 改用 `car(setof(prop obj~>prop prop~>name==name))` 查询已有属性，保留包归属、实例类型、原刺激值和真实 CDF 字段检查。仍先检查两个测试台再修改，并逐项读回实际 CDF。

v2 加载时会释放旧脚本留下的只读引用；如果遇到可编辑引用则停止，保留可能未保存的修改。v1 文件及日志保留。无需重新生成库，也无需修改工艺库或重新配置环境。

## 操作步骤

1. 将同目录 `p1_fix_pulses_v2.il` 上传到 Linux 的 `/home/compute/l.hongyi/cadence_skywater/`。它是单个文件，不需要解压。
2. 若 `p1b_tb_rc` 或 `p1b_tb_step` 原理图编辑窗口开着，保存并关闭这两个窗口；保持 Cadence CIW 开着。在 CIW 底部命令栏执行：

```lisp
load("/home/compute/l.hongyi/cadence_skywater/p1_fix_pulses_v2.il")
```

同一 CIW 里显示 `function ... redefined` 是载入新版函数的提示。修复完成应有两条 `P1_PULSE_SOURCE_SAVED`，最后是：

```text
P1_PULSE_REPAIR_V2_DONE: 2 sources saved. Next rerun native audits; NOT A SIMULATION PASS.
```

3. 看到完成标志后，在 **Linux 终端** 执行完整的一行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job rc_step --retry
```

如果 MIM 尚未运行，也在 Linux 终端执行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job mim_ac --retry
```

每条命令都要完整复制，不能将 `.sh` 后的参数另起一条命令。

4. 完成后打包并回传新 ZIP：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

若 load 出现 `*Error*`，先停止后续仿真，回传 CIW 错误文字；日志为 `basic_design_v1_0_4/runs/p1_pulse_repair_v2.log`，如已创建会被 collect 自动收集。启动时因旧可编辑引用而停止的错误可能发生在新日志创建前，需保留 CIW 文字。不要通过删除 cell 或重新运行 create.il 处理。

## 修复范围与验证

| 测试台 / 实例 | 原理图 CDF 值 |
|---|---|
| p1b_tb_rc / VIN | v1=0, v2=0.1, td=1n, tr=1p, tf=1p, pw=5n, per=10n |
| p1b_tb_step / VINP | v1=0.8, v2=1.2, td=1u, tr=20n, tf=20n, pw=2u, per=5u |

这些分别对应 Spectre 的 val0、val1、delay、rise、fall、width、period。没有改变原设计的刺激数值或网表审查要求。

本地检查覆盖语法括号和字符串、函数调用清单（能检出 v1 的实际错误）、两个源的全部 14 个参数，以及原生网表审查的错误拒绝与正确输入回归。**本地没有 Cadence，因此这些检查不是 SKILL 执行通过或仿真通过。** 被动件判据与最终性能仍待真实结果复核。

属性遍历方式参考 [Cadence 官方论坛的属性读取示例](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/15020/changing-cdf-property-display-value-via-skill)；只读模式及 dbClose 行为参考 [Cadence 工程师的 IC616 示例](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/30719/saving-designs-in-virtual-memory-to-disk/1338443)。

# 基础器件复核与旧 OTA 入口：1.0.4p2

本包解决电阻和 RC 的旧验收判据问题。它只更新本地运行／分析脚本，读取已有真实结果并另写复核记录。无需 CIW load、重新创建 cell 或重跑已完成的无源仿真。

## 前面一直在测什么、改什么

| 测试 | 要确认什么 | 已有结论 |
|---|---|---|
| NMOS / PMOS DC | 尺寸、端口、模型与 Spectre 的连接正确，栅压扫描产生合理漏电流 | 已跑通 |
| 工艺电阻 DC | 实际 I–V 和阻值，避免把界面显示值误当成恒定模型值 | 实测约 1.231 kΩ；与电压相关模型方程吻合 |
| MIM 电容 AC | 补偿电容的单位、几何与电容量正确 | TT/27°C、0.9 V 偏置下约 34.62225 fF，本次通过 |
| RC 阶跃 | 脉冲源参数、充放电过程、瞬态数据和时间单位正确 | 脉冲源已修复；模型参考 42.9836 ps，实际约 42.9852 ps |

重复修改主要来自三个方面：生成器使用了错误的 CDF 字段／函数；终端启动环境与已经打开的 Cadence 不一致；分析器使用了不适合真实工艺模型的理想 R/C 判据。这些是迁移工具和判据问题，不是用户必须反复手工调电路。

此前确实进行过器件映射：部分 MOS 宽度适配学校 CDF 精度，M7 因单指 50 µm 上限拆成两只 36.1 µm 并联管。原尺寸、差异和并联映射仍保留，需在 OTA 阶段检查性能影响。本包不再改这些尺寸。

## 第一步：上传并安装修正包

将 `project1_basic_runtime_fix_v1.0.4p2.zip` 上传到 Linux 的 `~/cadence_skywater/`。

在 **Linux 终端** 依次执行，每行单独一次回车：

```bash
cd ~/cadence_skywater
unzip project1_basic_runtime_fix_v1.0.4p2.zip
bash project1_handoff/basic_runtime_fix_v1_0_4p2/apply.sh
```

预期：`P1_RUNTIME_PATCH_APPLIED: 1.0.4p2`。已安装时显示 `ALREADY_APPLIED`。

安装位置仍是原来的 `project1_handoff/basic_design_v1_0_4/`，版本在 manifest 内更新。旧脚本备份到 `patch_backups/v1_0_4p2/`；原始仿真目录、site.json、原理图及 create.il 不变。若提示冲突或哈希不匹配，保留文字回传，不删除原文件。

## 第二步：复核现有三项数据

在 **Linux 终端** 执行完整一行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh recheck-passives
```

这条命令不启动 Spectre，也不操作原理图。它会检查原生网表、分析输入、日志、波形及哈希，再重新计算指标。

预期：

```text
res_dc RECHECK PASS original PASS FAIL
mim_ac RECHECK PASS original PASS PASS
rc_step RECHECK PASS original PASS FAIL
P1_PASSIVES_RECHECK_PASS ...
```

`original ... FAIL` 是被保留的旧判据结果；新复核存放在独立的 `runs/passive_reviews/<时间>/review.json`。只有三项全部通过，才进入下一步。

若出现 STOPPED 或 FAIL，执行本文最后的 collect，回传结果及终端文字；无需重复运行相同仿真。

## 第三步：旧 OTA 标称测试

复核通过后，在 **Linux 终端** 执行：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --group nominal --retry
```

这次才是开始实际运行旧 OTA 的四项标称测试：

1. `P01_op`：静态偏置、器件工作区与功耗。
2. `P01_ac`：低频增益和开环频率响应。
3. `P01_loop`：反馈环路交越、带宽和相位裕度。
4. `P01_step`：闭环阶跃、压摆率和建立时间。

条件为 TT / 1.8 V / 27°C。程序顺序执行；若某项工具运行或性能判据失败，会停止并保留结果。原有 PVT 入口仍在，先回传这四项结果复核，再推进剩余条件。不要把这一步的成功当成新版前端或 ADC 达标。

## 最后：打包回传

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

把生成的新 ZIP 下载并发回当前任务。新的无源复核与旧的所有失败记录都会包含在里面。

## 本地验证及剩余范围

补丁通过 11 项本地检查，其中包含原包的 17 项回归；检查了真实返回数据复核、错误数据拒绝、证据变化后阻止复用、安装重复执行、冲突停止及失败回滚。Linux 运行文件检查了 Python 3.6 语法兼容性。

当前还没有在学校执行本补丁；本地复核使用的是你返回的真实 Spectre CSV。模型文件逐层依赖、统计模型、噪声、PVT、旧 OTA 性能和物理验证仍各有自己的验收，不能由基础测试推定通过。

完整判据、公式和来源见 `payload/passive_criteria.md`。

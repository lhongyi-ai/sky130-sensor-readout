# 旧 OTA 工作点导出修复 1.0.4p3

## 本次在测什么、失败在哪里

P01_op 测旧 OTA 在 TT / 1.8 V / 27°C 的静态偏置、供电功耗以及 13 只 MOS 是否处于需要的工作区。本次 Spectre 已在 11 次迭代内收敛，0 errors、0 warnings、3 notices；输出 0.900012033 V，供电电流 151.015357 µA，对应供电功耗约 271.827642 µW。

器件数据导出失败：学校模型还有内部 MOS 层级。例如真实保存的器件名称为 `XOTA.M1.msky130_fd_pr__nfet_01v8`，旧脚本却读取 `XOTA.M1`。因此 op_devices.csv 只有表头，全部 65 次参数读取为空。旧 OCEAN 输入按逐条命令执行，报错后仍执行了写 COMPLETE 的命令；Python 最后检查出缺失数据，正确保留为 FAIL / NOT_RUN。

错误来自生成的结果读取脚本。不是已经确认的晶体管工作区失败，也不是仿真未运行。

## 本次改动

- 使用返回 PSF 中已经出现的 13 个内部 MOS 名称；读取前选择 dcOpInfo，并检查可用器件名称。
- 导出 ids、gm、gds、vds、vdsat，以及每行对应的原始器件名称。
- 一个受保护的导出操作中完成全部步骤；错误立即返回非零退出状态。Python 同时检查错误日志、13 行数据、有限值及映射，不仅检查 COMPLETE。
- 从已有 PSF 创建独立恢复记录，重新导出 P01_op。复制保存原 PSF 和输入哈希，不修改原失败 attempt；不再运行这次 P01_op 的 Spectre。
- 电路、尺寸、补偿参数、刺激、仿真选项和性能门槛不变。

日志中的 bad pivoting 是数值求解提示；本次仍收敛。该提示完整保留，后续结合器件工作点及 AC／阶跃继续复核，没有为了消除提示而改动仿真选项。

## 只需上传一次，执行一个继续入口

1. 上传 `project1_basic_runtime_fix_v1.0.4p3.zip` 到 Linux 的 `~/cadence_skywater/`。
2. 在 **Linux 终端** 依次执行以下三行。无需在 CIW load，不重建原理图：

```bash
cd ~/cadence_skywater
unzip project1_basic_runtime_fix_v1.0.4p3.zip
bash project1_handoff/basic_runtime_fix_v1_0_4p3/continue_nominal.sh
```

这个入口依次进行：安装修复 → 复核已有三项无源数据（不重仿）→ 从现有 PSF 恢复 P01_op 导出 → 通过后继续 P01_ac、P01_loop、P01_step → 自动 collect。

预期先显示 `P1_RUNTIME_PATCH_APPLIED: 1.0.4p3`，随后 `P1_PASSIVES_RECHECK_PASS`。恢复成功时显示 `P01_op PASS PASS RESUMED_EXPORT ...`。进入标称组时 P01_op 显示 ALREADY_ATTEMPTED，是跳过刚恢复成功的结果，随后运行另外三项。

任一步失败会停止后续测试并自动打包已有结果。请把最后输出路径对应的新 ZIP 下载发回本任务，并保留终端文字。不要因为 FAIL 就再次执行同一个入口；先分析该次报告。

若安装失败且尚未进入运行阶段，入口不会收集不完整安装的报告，请直接回传错误文字。旧脚本保存在 `patch_backups/v1_0_4p3/`。旧 1.0.4p2 数据、原理图及所有失败记录保留。

## 验证状态与依据

本地检查包括：实际 PSF 中存在全部 13 个内部器件名称；旧的“错误 + COMPLETE + 退出码 0”会被拒绝；缺行、非数值和错误器件映射仍拒绝；恢复流程仅调用 OCEAN、保持原 PSF 和失败记录；安装与回滚、原包 17 项回归以及无源数据复核。

本地没有 OCEAN/SKILL 运行环境，恢复流程的数值单元测试是合成测试夹具，未用来宣布 OTA 通过。实际器件参数和饱和区状态仍待本次学校导出。

接口依据：[Cadence 工程师关于 selectResult、outputs、getData 读取工作点结构的示例](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/36112/getting-report-into-a-list)；[Cadence 关于 errset 与 exit(1) 的说明](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/59814/how-to-get-exit-code-0-when-there-is-a-skill-error-in-a-skill-script/1399235)。内部 MOS 名称依据本次返回文件，未猜测其他工艺库命名。

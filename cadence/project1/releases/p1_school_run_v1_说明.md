# project1 固定学校环境入口 v1

最新报告中，MIM 与 RC 都在 OCEAN 启动时报告 `exec: virtuoso: not found`。它们没有开始网表生成或 Spectre 仿真。之前手动设置的 PATH 等变量只对当时的终端有效；原 `p1_run.sh` 只隔离 Python 库，没有完整恢复学校工具环境。

`p1_school_run_v1.sh` 把之前成功运行的环境统一加载后，再调用现有 `p1_run.sh`。它固定匹配 IC618 的 Virtuoso 路径、CDSHOME、共享库路径和用户已确认的许可证服务器地址，保留 Python 库隔离。设置只作用于这次启动及其子进程，不更改终端启动文件、系统安装、工艺库、原理图、site.json 或已有运行状态。

## 上传一次

将 `p1_school_run_v1.sh` 上传到学校 Linux 的：

```text
/home/compute/l.hongyi/cadence_skywater/p1_school_run_v1.sh
```

这是单个文件，无需解压，也无需 chmod 或 CIW load。原 `basic_design_v1_0_4` 及已安装的 1.0.4p1 补丁继续使用。

## 后续从任何 Linux 终端执行

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job mim_ac --retry
bash ~/cadence_skywater/p1_school_run_v1.sh run --job rc_step --retry
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

把两项输出和 collect 打印的报告 ZIP 回传。仍按工具状态与性能状态分别判断，入口能启动不代表测试通过。原电阻的模型一致性复核已另行保留，旧 CDF 比较失败记录不变。

若第一条出现 `P1_SCHOOL_ENV_STOPPED` 或 `ENV_BLOCKED`，先回传错误，不连续重试；新运行目录保留实际工具日志。若工具状态为 PASS、性能状态为 FAIL，保留结果继续收集另一项独立基础测试，待三项原始数据齐全后统一修正被动件判据。

后续查询、回传也用同一个入口：

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh summary
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

入口仅恢复已观测到的客户端配置。许可证地址不是许可证文件或密钥；能否实际取得许可证仍由学校服务器决定。此版本的本地检查覆盖 shell 语法、未配置终端中的变量恢复、参数传递、Python／Cadence 环境隔离和子进程退出码。没有在本地运行学校 Cadence。

# 新上传包的放行门（2026-09-13）

本目录新增 `release_gate.py`，用于减少学校 Linux 上的损坏包、混版本、依赖和兼容性事故。**没有构建或发布新版前端上传包：新版前端尚未冻结。** 没有操作学校环境，也没有改动本目录已有 `regression*.log/json`。

本次只运行了 13 项合成小包测试：完整本地包仍被缺少现场 canary 阻止；损坏 ZIP、多个根目录、漏列文件、SHA 错误、混版本、CRLF、内部路径空格、Python 新语法/非 3.6 标准库及旧/mock canary 均被拒绝。详见 `release_gate_tests.log`。这些是**本地工具测试，不是学校通过记录**。

## 使用

```sh
python3 release_gate.py '/path with spaces/new_package.zip' --output preflight.json
python3 release_gate.py '/path with spaces/new_package.zip' --canary school_evidence/canary.json --output release_check.json
```

无合格现场 canary 时退出码为 **2**，`batch_release_allowed=false`。第一条可以得到 `local_preflight_pass=true`，仍不会放行批量；不需要为此反复上传新补丁。门控只读取 ZIP，不解压、不安装，也不启动仿真。

ZIP 外部存放路径可以含空格，调用时正常加引号。为了消除学校脚本路径传播的不确定性，新发布 ZIP 的内部目录和文件名不接受空白字符。

## 新包固定合同

ZIP 中仅有一个顶层目录；不允许绝对路径、`..`、反斜杠、符号链接、重复或不规范路径。这个根目录包含 `release_gate_manifest.json`，格式为：

```json
{
  "release_id": "frontend_frozen_version_here",
  "version": "frozen_version_here",
  "root_dir": "frontend_frozen_version_here",
  "files": {
    "run.py": "完整文件的 SHA-256",
    "start.sh": "完整文件的 SHA-256"
  }
}
```

`files` 必须逐一覆盖 ZIP 内全部非目录文件，唯一例外是清单自身。整个 ZIP 的外层 SHA 约束清单自身，因此不要求不可能的自哈希。若存在 `package_manifest.json`，其版本必须与新包清单一致；新包不能混入历史 `patch_backups`。检查器同时读取完整 ZIP，验证 CRC 与每个文件 SHA。

所有包内 `.py` 都按**学校执行文件**检查 Python 3.6 语法和 3.6 标准库 imports；本地专用构建/分析脚本应留在本地。禁止 `numpy`、`dataclasses`、future annotations、海象运算符等依赖/语法；对已知较新标准库 API 及动态加载/执行要求显式处理，不能靠静态 imports 放行。`.py/.sh/.il/.ocn` 不得带 CRLF、孤立 CR 或 UTF-8 BOM。

静态规则是保守检查，不能证明所有动态标准库 API、CDF 回调、SKILL 函数、OCEAN 信号导出都兼容；这正是必须留有学校实际 canary 的原因。检查器自身使用 Python 3.6 语法和标准库；本轮在本机做了 3.6 语法解析，**没有声称在真实 Python 3.6.8 执行过**。

## 二进制桥和学校架构

若新包包含 `.so`、带版本后缀的 `.so.N` 或任何 ELF 文件，清单必须增加 `school_target_machine`，当前支持 `x86_64` 或 `aarch64`。检查器读取 ELF magic、class、endian、version 和 e_machine：x86_64 必须为 ELF64/little/e_machine=62；aarch64 必须为 ELF64/little/e_machine=183。禁止未声明目标、架构不一致或把本地 ARM 桥直接放入 x86_64 学校包；Mach-O（包括常见 universal/fat）和非 ELF 的 `.so/.dylib` 被拒绝。纯 Python/SKILL 前端包没有 native 文件时，不要求这些字段。

含 native 文件的实际学校 canary 还必须记录 `environment.machine`，与清单目标完全一致，并增加 `steps.native_load`。该步骤遵守同一 V1 完成标志协议，`modules` 数组逐一列出所有包内 native 文件的相对路径，日志保存实际加载结果。例如 `modules: ["cosim_controller_fixed.so"]`。加载失败不得写完成标志。

本轮新增两个**合成 ELF 头**测试：ARM ELF 发往 x86_64 被拒绝；正确 x86_64 ELF 元数据只能通过本地文件头检查，仍被缺少学校 canary 阻止。ELF 头正确不证明链接库、glibc/ABI、模块加载、仿真器接口或连续转换功能兼容；实际学校入口必须真正加载模块并跑相应最小闭环。没有创建虚假的学校证据，也未将本地桥发布给学校。

## 同一包学校 canary 的最低证据

正式包先在学校 **Linux / Python 3.6.8 / IC6.1.8 / Spectre 21.x** 串行执行一个最小 canary，覆盖 Python 编译、原生 cell 创建或读取、一例 Spectre 仿真、结果导出。保存每步完整日志和退出状态；让实际执行入口写出 `canary.json`，不要在本地手填 PASS：

```json
{
  "package_zip_sha256": "学校实际执行那份 ZIP 的完整 SHA-256",
  "release_id": "与新包完全一致",
  "execution_kind": "ACTUAL_SCHOOL_CADENCE",
  "mock": false,
  "environment": {
    "platform": "Linux",
    "python": "3.6.8",
    "virtuoso": "IC6.1.8 实际版本输出",
    "spectre": "21.1 实际版本输出"
  },
  "completed": true,
  "exit_code": 0,
  "steps": {
    "python_compile": {"completed": true, "exit_code": 0, "log": "python.log"},
    "native_create_or_open": {"completed": true, "exit_code": 0, "log": "native.log"},
    "spectre_canary": {"completed": true, "exit_code": 0, "log": "spectre.log"},
    "result_export": {"completed": true, "exit_code": 0, "log": "export.log", "outputs": ["result.csv"]}
  },
  "evidence": {
    "python.log": "SHA-256",
    "native.log": "SHA-256",
    "spectre.log": "SHA-256",
    "export.log": "SHA-256",
    "result.csv": "SHA-256"
  }
}
```

现场退出码 0 和 `completed=true` **不足以通过**：检查器还读取每步原始日志，拒绝 `*Error*`、`ERROR (SPECTRE-...)`、`FATAL`、`no such vector`、未定义函数、CDF 初始化失败、导出缺失/失败、Python traceback 等已知致命标志。`result_export` 还必须列出实际非空导出文件并通过 SHA 核对。

现场执行入口必须在对应子进程完成、输出内容核验通过且导出文件存在以后，在该步日志中**恰好写出一次独立完整行**：

```text
P1_CANARY_STEP_V1 COMPLETE <step_name> <同一ZIP的64位SHA256> <同一release_id>
```

`step_name` 分别为 `python_compile`、`native_create_or_open`、`spectre_canary`、`result_export`。不能预写完成标志，不能从 JSON 的 completed 字段推导，不能在错误后补写标志来覆盖失败；日志即使有标志但包含上述错误也会被拒绝。旧版或缺少此 V1 标志的 canary 不复用。本轮**尚未生成带此协议的新学校入口**，所以新包仍未放行。

合成负测专门覆盖“同包、exit 0、哈希正确、标志齐全但原始日志报错”及“同包、exit 0、缺完成标志”。canary / steps / evidence / environment 类型错误会被整理为阻止放行的结果，不会用异常退出假装有效报告。协议和哈希仍只检查证据一致性，不能认证机器来源；必须保留人工原始日志审查。

所有证据文件位于 `canary.json` 同目录或子目录，必须实际存在并匹配哈希。换 ZIP、改版本或改日志后，旧 canary 立即失效。检查器验证绑定和声明的一致性；学校来源与电路正确性仍须结合原始日志审核，哈希本身不能证明日志来自哪台机器。

过往问题包括 Cadence 库路径污染系统 Python、CDF 初始化/回调差异、学校 SKILL 函数不可用、器件宽度被 PCell 截断，以及结果导出名称不兼容。这些需要现场最小运行才能暴露。`BATCH_RELEASE_ALLOWED` 只表示本包完成上述交付前置条件，不意味着电路性能、噪声/PVT 或版图签核通过。

复现本地防误判测试：

```sh
python3 test_release_gate.py
```

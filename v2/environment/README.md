# 开源环境资格与复现边界

Cadence 依用户要求暂停。本目录的证据属于开源工具／公开 SKY130A PDK，不是 Cadence 资格。

原资格使用 IIC-OSIC-TOOLS 镜像 `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`，PDK 安装在容器 `/foss/pdks/sky130A`，解析版本 `026824c7969ce6f4fc9678e6ca04b0a06a596c4b`。历史容器名 `sky130-v2-open-work`，历史记录保留。

2026-09-10 的实际运行容器为 `sky130-v2-resume-20260910`，使用同一镜像、同一 PDK，网络关闭。完整工作副本位于 `/Users/stanley/Documents/ChatGPT/Analog Circuit Project/sky130-two-stage-ota`；其根目录只读挂载到 `/repo`，仅新版目录可写挂载到 `/repo/v2`。新运行不写旧工作副本，也不启动 Cadence。

额外发现：现成 VACASK 可运行固有 RC 随机噪声，但其 BSIM4v8 与当前 ngspice47 选中的 SKY130 BSIM4v5 噪声不等价，资格未通过。见 [本轮噪声资格](../verification/noise_20260910/README.md)；软件存在不等于工艺噪声可用。

## 已执行的独立资格

| 入口 | 证据 | 范围 |
|---|---|---|
| `qualify.py` | [device_qualification.json](results/device_qualification.json) | 45 个单管工艺温压点、200 个真实失配实例、重复／关闭统计种子控制，共 247 次仿真 |
| `qualify_cap_multiplier.py` | [cap_multiplier_qualification.json](results/cap_multiplier_qualification.json) | 600 个真实 PDK 电容实例，分别验证单元、仅 m=64、m=mult=64 的均值和局部失配缩放 |
| `qualify_physical.py` | [physical_qualification.json](results/physical_qualification.json) | 自生成 MIM 和 NMOS 小版图，DRC/LVS、含电容寄生的仿真闭环 |

在该容器内调用相应 Python 脚本即可复现；每次生成带时间戳的输出目录、源码快照、原始仿真文件、日志和结构化报告。

实际发现：只设置 MIM `m=64` 可以正确缩放标称电容，但不能据此假设局部随机失配按 sqrt(64) 缩小。独立控制试验验证了本 PDK 中 `m=64 mult=64` 的正确局部统计缩放。原错误假设的失败报告保留，不覆盖。

这些 200 样本是器件或电容构造检查，不是 200 颗完整芯片的良率。统计模型未验证空间梯度和版图相关系统性失配。小版图闭环中的提取是电容寄生；[采样开关物理实现](../physical/adc_switch/) 和数字宏另有真实 RC 提取，不能混为一项。

仅保存自有设计、工具／模型版本、哈希、结果和可公开的必要许可说明，不复制受限制规则、许可证、账号或学校配置。

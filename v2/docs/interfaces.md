# 接口与数据定义

## 模拟边界

最终核心计划使用 VINP/VINN、VDD/VSS、VREFP/VREFN、VCM。
行为模型输入为 VINP−VINN，单位 V；输出满量程为 −0.4～+0.4 V。
参考与共模是外部提供的电压，不包含片上带隙参考。
在非标称 VDD 下，计划 VCM=VDD/2、VREFP=VCM+0.2 V、VREFN=VCM−0.2 V，以保持 0.8 V 差分满量程；这些仍待器件耐压和开关功能验证。

12-bit LSB = 0.8/4096 = 195.3125 µV。输入等效 LSB 还需除以前端增益。
每个转换门限等于 −0.4+k×LSB；恰好位于门限的值取上方码。
码中心对应电压 (code+0.5)×LSB−0.4，校准按码中心坐标定义，避免隐藏半 LSB 偏移。
超出范围的模型 ADC 会饱和到端码，但前端本身的电源限幅/过载恢复未建模。

## 数字接口

| 信号 | 语义 |
|---|---|
| clk | 外部 1.6 MHz；当前理想时钟测试采用 50% 占空比 |
| rst_n | 异步低有效复位；取消未完成转换，清除输出有效状态 |
| start | 在 ready=1 时被接受；持续保持高可请求连续转换 |
| gain_sel | 00→1、01→4、10→16；11 拒绝该请求 |
| ready / busy | 互为反相；busy 指请求反压，不是内部模拟活动标志 |
| gain_latched | 当前在处理或刚接受的增益 |
| sample_en | 4 个完整采集周期内为高 |
| trial_code | 提供给后续 CDAC 开关译码的 12-bit 试探码；不是实际模拟开关波形 |
| comparator_evaluate | 决策周期后半段要求比较器求值；物理实现待验证 |
| comparator_bit | 比较结果：1 保留当前试探位；0 清除；按文档的上升沿采样 |
| data_valid | 本次转换完成时为高一个周期 |
| data / data_gain | 同一完成帧的原始码和增益，直到下次完成/复位前保持 |

最后一个决策周期 ready=1，可在完成旧帧的边沿接受新帧。
此时 data_gain 属于旧帧，gain_latched 已属于新帧；外部校准必须使用 data_gain。
非法 gain_sel 不取消正在完成的旧帧，也不启动新帧。

## 外部校准

每档三点输入是该档允许幅度的 −80%、0、+80%；三点各保留 4096 次稳定后采样的平均值与标准差。
系数文件记录实例、增益、标称电压温度、训练点、斜率、截距和误差。
验证点取 −90%～+90% 范围的独立网格，排除所有训练点，每点平均 2048 次。
浮点校准结果不裁剪、不重取整；原始 12-bit 数据始终保存。

为了展示固定标定的局限，实验另注入 +100 µV 输入失调漂移，保持原系数不变。
这是合成敏感性测试，不是某一温度的真实 SKY130 漂移。

## 结果状态

- LOCAL_MODEL_AND_DIGITAL_TESTS_PASS：本地模型与 RTL 测试通过。
- PARTIAL_PDK_FEASIBILITY_NOT_VERIFIED：M2 尚未完整通过。
- NOT_RUN_REQUIRES_TRANSISTOR_MODEL：测试矩阵已定义，但没有真实电路结果。
- SYNTHETIC / BEHAVIORAL：只能作为预算和分析方法验证。

不得将上述状态自动提升为 POST_LAYOUT、PVT_PASS、MISMATCH_PASS 或 SILICON_MEASURED。

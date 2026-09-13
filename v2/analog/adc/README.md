# SKY130 ADC analog implementation — development evidence

这里是实际 SKY130 MOS、电阻与 MIM 电容的 ADC 模拟电路，不是行为级 ADC。它仍是**未完成规格验收的晶体管级设计**；没有 Cadence 原生图、完整 ADC 版图或硅测数据。项目级完成状态以 `v2/integration` 和顶层审计为准，不能把本目录的独立模块通过数相加变成全芯片通过。

## 电路与边界

`adc_blocks.spice` 提供 MOS 传输门、StrongARM 动态比较器、静态 CMOS 决策保持锁存器、参考选择逻辑、真实 MIM 单元和 12 位常规二进制 CDAC。保持锁存器在动态比较器复位时仍保存 Q，满足真实数字控制器采样后的 hold 要求。

每侧电容为 2048+1024+…+1 加一个 dummy，共4096个 3×3 µm 单元。实际安装的 continuous PDK 模型包含每边0.15 µm尺寸修正，单位名义电容19.845 fF，每侧81.28512 pF。`m=COUNT`实现名义并联数量，`mult=COUNT`使模型失配标准差按单位数量正确缩放；仅设置`m`不能宣称正确统计匹配。该语义已由环境资格测试独立验证。8192个基本单元的73728 µm²只是名义电极面积，绝非完整核心版图面积。

四个独立顶层，均由 `generate_analog_wrapper.py` 生成：

| 文件／subckt | 用途 | 当前选择状态 |
| --- | --- | --- |
| `adc_analog12.spice` / `adc_analog12` | 顶板采样、参考底板切换、直接比较器 | 保留的首次完整转换基线 |
| `adc_analog12_bottomsample.spice` / `adc_analog12_bottomsample` | 顶板夹到VCM，底板采输入 | 独立对照，未缓冲比较器仍有切换干扰失败 |
| `adc_analog12_bottom_preamp.spice` / `adc_analog12_bottom_preamp` | 底板采样后加真实连续时间预放大器隔离比较器 | 候选；另需包含 `adc_preamp.spice` |
| `adc_analog12_bottom_preamp_lvtref.spice` / `adc_analog12_bottom_preamp_lvtref` | 预放大器＋按位权定尺寸的双LVT采集／参考TG | 建立时间修复候选；另需 `adc_reference_candidate.spice`，顶板夹位TG仍是标准Vt |

共同端口顺序：

```text
INP INN Q QB SAMPLE SAMPLEB ACQ CONV EVAL
B11 B10 B9 B8 B7 B6 B5 B4 B3 B2 B1 B0 RP RN VCM VDD VSS
```

`SAMPLE/SAMPLEB`先打开顶板输入／夹位路径；随后`ACQ`打开底板采集路径；非重叠时间后`CONV`连接底板参考；残差建立后`EVAL`触发比较。Q为高表示输入差分大于当前试探阈值。固定码测试中的外部相位是理想有限沿激励，不是片内时钟电路。真实 MOS 相位发生器及原 RTL 闭环在 `v2/integration` 单独验证。

偏移二进制阈值为`0.8*code/4096 - 0.4 V`。dummy不是随意接VCM：顶板采样时P dummy接RP、N dummy接RN；底板采样时相反，且比较器极性反转，才能保持同一阈值定义。早期错误dummy造成约1 LSB整体位移，其失败没有删除，也没有用校准掩盖。

`adc_preamp.spice`是独立候选，不替换原比较器：实际NMOS差分对、75 kΩ PDK多晶电阻负载、beta-multiplier偏置及启动电路，没有理想IREF。其作用是降低动态锁存器对浮置CDAC的反冲；预放大器的噪声、失调和大信号恢复仍须计入预算。

参考开关的子电路默认尺寸为WN0.84/WP1.68，但实际wrapper已经按位权平方根放大，最高几位封顶WN8/WP16；**MSB并非默认小尺寸**。`run_reference_switch.py`中的最小开关驱动MSB测试只是尺寸反例，不能把其失败归因于冻结的MSB。实际MSB对照使用`--actual-only`；新双LVT支路另存`adc_reference_candidate.spice`，未擅自替换冻结电路。

参考诊断默认`--reference-mode fixed`保持RP/RN为1.1/0.7V，输入共模仍随VDD/2。`tracking`模式令RP/RN=VDD/2±0.2V，低电源时变为1.01/0.61V。两种外部条件不能混为一谈，不能拿固定参考模式的误差直接解释跟踪参考模式的整ADC结果。原规格只给标称参考值，最终外部参考规则必须明确冻结，或同时覆盖两种模式。

已实际对照的SS低压冷角tracking模式中，W8/P16标准Vt MSB支路驱动20.321pF等效负载，从0.61→1.01V切换后300ns仍差−124.56mV；W13.44/P26.88、LN0.15/LP0.35的双LVT候选同条件降至−0.000584µV。这里20.321pF是浮置MSB的串联等效下界，40.643pF则是top夹位时的采集负载上界，均为真实MIM实例。负载边界实验不替代整阵列的相位负载、注入、失配、寄生和噪声资格。

## 已验证内容与不能推出的结论

- 裸比较器：45 PVT组合×两种±0.25 LSB输入均正确，另有10个TT输入幅度点。输入持续由350 Ω源驱动，**不是浮置CDAC条件**。
- 比较器保持接口：六组条件、每组两次相反决策，5 fF数字负载；已测最长解析时间约8.23 ns，复位后仍保持输出。不能将其推广为全PVT的时序签核。
- 原标准Vt采样TG：51个标称点通过，但后续独立物理测试发现SS低压冷角严重建立失败。该TG未因此获得PVT资格。新的低阈值输入TG及其版图在 `v2/physical/adc_switch` 独立推进，不能直接替换参考小开关。
- CDAC：17个名义码点；200个真实PDK统计电容阵列对的全码电荷守恒计算。统计结果只覆盖电容失配，不含比较器、开关、前端、布线和空间梯度，**不是200颗ADC或量产良率**。
- 比较器：200个真实`tt_mm`实例、1400次粗阈值决策。首次±3 mV范围仅括住143个实例，57个不在范围内。后续扩大并细化，原失败及近阈值历史依赖均保留；固定校准结果及有限估计精度以对应JSON为准。
- 浮置CDAC六点对照：底板采样本身的比较前残差改善，但无preamp仍有3/6错误决策；同参考条件下加实际preamp后6/6正确。这是模块交互的工程改进，**不是全码无缺码／12-bit精度证明**。

整个真实 SAR 的逐位控制必须读 `v2/integration/results`：那里使用原`SAR RTL`的实时数字／SPICE闭环，不是事后根据理想输入预先生成正确码。本目录早期`run_sar_transistor.py`的B源寄存器尝试发生收敛／超时，已经被该工作流取代，不能作为成功验收入口。

## 可复现入口

在固定IIC容器内设置 `SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice`，按需运行以下脚本。共享容器一次只启动一个重仿真worker。

```sh
python3 /repo/v2/analog/adc/run_adc.py --suite full --jobs 1
python3 /repo/v2/analog/adc/run_latch_interface.py
python3 /repo/v2/analog/adc/run_cdac_mismatch.py
python3 /repo/v2/analog/adc/run_comparator_mismatch.py
python3 /repo/v2/analog/adc/run_analog_wrapper.py --architecture bottom_preamp --reference-ohm 1 --external-reference-cap-f 1e-8
python3 /repo/v2/analog/adc/run_preamp.py --jobs 1 --resume
python3 /repo/v2/analog/adc/run_preamp_pvt.py --jobs 1 --resume
python3 /repo/v2/analog/adc/build_summary.py
```

`generated/`保存实际SPICE测试台，`results/`保存日志／波形／JSON，`results/history/`保存失败与被修订测试的历史。新增仿真保存逐次source hash和源快照；`summary.json`为范围明确的验收索引，`manifest.json`为文件哈希清单。当前源哈希不冒充所有历史测试运行时的源哈希。

## 必须保留的风险

没有完整ADC全码晶体管INL/DNL、含真实器件噪声的16384点SNDR、完整200系统失配、全ADC版图／PEX或Cadence验证。连续时间preamp的`.noise`只能证明其局部静态小信号噪声；输出频谱按DC增益折算与直接积分输入等效谱不同，两者分别报告。不能把无噪声瞬态FFT、kT/C公式或人为白噪声源冒称时变比较器的器件噪声验证。

比较器输入对曾遇到安装版PDK/ngspice对“字面宽度”和“表达式宽度”采用不同角模型的真实不对称。独立同电压晶体管电流对照证实：两腿使用一致表达式后恢复匹配。仅改参数名、仅避开8 µm边界均不能修复，已经保留这些被证伪的假设；不将未经证实的内部原因当作结论。

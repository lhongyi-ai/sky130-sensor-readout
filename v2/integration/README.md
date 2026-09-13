# 真实晶体管与 SAR RTL 联调

本目录使用 ngspice 的 XSPICE `d_cosim` 和 Verilator，运行原始、可综合的 `rtl/sar_controller.v`。不是用另一个软件 SAR 算法替代数字控制。接口方法见 [ngspice 官方手册](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf) 的 HDL co-simulation 部分。

## 三个不同层次的证据

1. `qualify_cosim.py --vdd 1.62`（也运行 1.8、1.98）：ADC 是理想测试夹具，仅验证逻辑端口、极性和连续 100 kS/s 时序。不能证明模拟 ADC 正确。
2. `qualify_phases.py`：真实 SKY130 MOS、电阻和 MIM 组成的非重叠相位电路；45 个工艺温压组合独立检查，保留实际负载、所有波形和源文件快照。
3. `run_adc_cosim.py`：真实 ADC 与原 RTL 连续转换，可显式加入冻结前端。默认真实相位电路；`--phase-source ideal` 仅用于保留对照实验。

示例（容器内）：

    python3 /repo/v2/integration/qualify_cosim.py --vdd 1.8
    python3 /repo/v2/integration/run_adc_cosim.py --input-v 0.123

新的底板采样／前置隔离放大候选使用显式参数，不覆盖原 ADC：

    python3 /repo/v2/integration/run_adc_cosim.py \
      --adc-wrapper /repo/v2/analog/adc/adc_analog12_bottom_preamp.spice \
      --adc-subckt adc_analog12_bottom_preamp \
      --adc-preamp /repo/v2/analog/adc/adc_preamp.spice

`--frontend` 必须指定待验证前端文件。`--gain` 为 1、4、16；输入参数 `--input-v` 指理想放大后希望送到 ADC 的差分电压，传感器实际刺激自动除以增益。源阻抗保留在传感器与前端之间，不能在加入前端时消失。

前端隔离电阻必须按冻结实验显式指定 `--frontend-riso`，不能因为源码默认值不同而偷换负载条件。例如 FDDA5 的已复核快照使用每端 2200 Ω。FDDA10 当前有共模振荡，不应将其接入后用短码容差宣称合格前端。

`candidates/20260908T045601001817Z/` 保存低阈值参考开关、真实前置放大和四 MOS 补偿顶板钳位的组合快照。该候选只完成标称与 SS／1.62 V／−20 °C 各一个 0.123 V 输入的完整转换，均输出 2677。其 manifest 保持 `UNQUALIFIED_INTEGRATION_CANDIDATE`。运行时应显式传入该目录的 wrapper、blocks、preamp，并分别 `--extra-include` 该目录的参考开关和采样开关文件；不能混入其他版本。快照生成器只替换两个顶板钳位，补偿晶体管必须接被保持的 B 节点，A/B 不能互换。

逻辑桥报告不仅需要 PASS，也必须与当前控制器、接口包装及桥接脚本的哈希、供电和仿真后端一致。源码改变后必须重新资格检查。

`--reference-r`、`--reference-c-nf` 描述外部参考／共模源阻抗和外部去耦，默认各 1 Ω、10 nF。`--source-r` 为每端 0／350／1000 Ω，`--input-cm-offset-mv` 为 −50／0／50 mV。参考电压相对 VDD/2 保持 ±0.2 V。

参考条件已显式区分：默认 `--reference-cm-mode tracking` 使 VREF±=VDD/2±0.2 V；`fixed` 保持外部参考为 1.1／0.7 V，但输入共模仍为 VDD/2。两者标称相同、供电变化时不同。原计划只给出标称参考，最终须冻结这个外部接口条件或覆盖两者，不能把一个模式的失败直接归因到另一个模式的电路。ADC 独立参考支路诊断的部分早期测试使用 fixed 模式。

大电路仿真显式保存所需观察节点，避免把所有内部节点波形都驻留内存。`--solver sparse`／`klu` 只切换数值求解器，不修改电路、转换次数、刺激或误差门槛。超时单列为未完成，不能从部分正确输出推断整项通过；旧的超时报告原样保留。

## 已知解释限制

- 短联调每个输入通常只有三次转换。2 LSB 原始码容差是定位连接／极性／时序错误的 smoke gate，不是放宽 INL、校准残差或 SNDR 目标。
- Verilator 接口日志的 `$realtime` 可能显示零；转换间隔用 SPICE 波形中的 data_valid 上升沿测量，不能拿日志零时间作时序证明。
- 数字电平桥仍是理想接口，不含数字标准单元功耗／延迟。真实数字宏的物理时序与功耗另有报告；最终必须在一致的顶层条件下整合，而非拼接最好值。
- MOS／电容／电阻使用真实 PDK，但本目录目前是原理图级。参考端瞬态电流和净供能有直接积分；不是完整芯片功耗终验。
- 新版功耗分析只积分两个 data_valid 上升沿之间的完整转换周期；单次转换没有足够完整周期，不输出平均功耗。早期报告的短窗口诊断值保留，但不得解释成全周期功耗。
- 当前合格流程没有证明动态比较器的器件大信号随机噪声被完整纳入。无噪声瞬态 FFT、连续前置放大器 `.noise` 或人工注入的独立随机源，都不能单独证明完整 ADC／系统 SNDR。需进一步资格确认相应的时变噪声方法；最终 Cadence 验证仍必须完成。
- Icarus co-simulation 挂起、旧相位对照、旧前端／旧 ADC 失败及每次源快照均保留。使用带时间戳的 `summary.json` 判断特定候选，不把 `latest` 文件当所有版本都通过。

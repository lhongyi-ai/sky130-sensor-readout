# 冻结采样开关文件与接口

先读 `results/sampling_switch_release.json`。只有下列最终四管版本属于
这次完整资格；历史 `artifacts/` 顶层和其他候选目录不得混入最终GDS。

| 用途 | 文件/单元 |
|---|---|
| 原理图级 SPICE | `candidates/adc_tgate_dual_lvt_dummy.spice` |
| 原理图子电路名 | `adc_tgate_dual_lvt_dummy` |
| 寄生后 SPICE | `artifacts/dummy_layout_final/adc_tgate_flat.rc.spice` |
| 寄生子电路名 | `adc_tgate_flat` |
| GDS | `artifacts/dummy_layout_final/adc_tgate_layout.gds` |
| GDS顶层单元名 | `adc_tgate_layout` |
| Magic原生版图 | `artifacts/dummy_layout_final/adc_tgate_layout.mag` 与同目录4个器件子单元 |
| 实体版图渲染 | `artifacts/dummy_layout_final/adc_tgate_layout.png` |
| DRC/LVS/提取记录 | 同目录 `layout.log`、`lvs.rpt`、`lvs.json`、`rc_extraction.log` |
| 45PVT完整逐点结果 | `results/dummy_w4w8_rc_full.json` |
| 满量程边界结果 | `results/dummy_fullscale_boundaries.json` |
| 所有最终原始波形 | `evidence/final_qualification/*.tsv.gz`、`evidence/fullscale_boundaries/*.tsv.gz` |
| 开源几何许可 | `THIRD_PARTY_NOTICE.md`、`LICENSE.sky130.txt` |

两个SPICE子电路的端口顺序都是 `A B EN ENB VDD VSS`，但A/B不对称。
A接驱动源；B接保持节点，dummy的两端都短接B。作为VCM顶板钳位器时：

```spice
.include /project/v2/physical/adc_switch/candidates/adc_tgate_dual_lvt_dummy.spice
XCLAMP VCM TOP TOP_EN TOP_ENB VDD VSS adc_tgate_dual_lvt_dummy
```

寄生后替换为：

```spice
.include /project/v2/physical/adc_switch/artifacts/dummy_layout_final/adc_tgate_flat.rc.spice
XCLAMP VCM TOP TOP_EN TOP_ENB VDD VSS adc_tgate_flat
```

`/project` 是示例项目根路径，需按实际位置替换，并从经验证的PDK引入
对应工艺角。仅默认 N4/.15、P8/.35、dummy比例0.5经过本资格；改尺寸、
改负载或换时钟边沿后应重新验证。不要把它直接套进所有参考MUX小开关。
各历史GDS/RC复用了演示单元名，只能导入选定最终版本，不能一起合并。

冻结SHA-256：

- 原理图源：`389d182342b2d1e88ba31530c6cc98d0e75756d8009126746d7d73b40d98d734`
- RC网表：`7497a012a94c1e48c1c7de7d13f61bfa4c709aec709d52faeafb06bf1867e2d5`
- GDS：`5e26038355c6f8ca3d10542af81bc53ca660998ca036aef55f5384585bb263e2`

本目录的独立A端阶跃测试不能替代真正CDAC底板切换下的系统钳位实验。
原理图/RC通过结果均使用公开SKY130开源流程，不是Cadence验证或硅测。

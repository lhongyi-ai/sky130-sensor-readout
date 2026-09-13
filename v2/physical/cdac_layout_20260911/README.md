# 12-bit 差分 CDAC：SKY130 实体单元放置版 floorplan

## 结论

这里已经把原先的二维分配表变成了一个可由版图工具打开的、真实 SKY130A MIM 电容层次化 floorplan：

- P、N 两侧各放置 **4356** 个真实 `sky130_fd_pr__cap_mim_m3_1` 单元；
- 每侧包含 **4096 个有效单位电容**和 **260 个边缘 dummy**；
- 因此顶层一共是 **8712 个物理 MIM 实例**，其中 **8192 个属于 ADC 的有效阵列**；
- Magic 对 P 侧、N 侧及差分顶层的 **placement-only DRC 均为 0**；
- KLayout 从最终 GDS 独立回读，确认顶层有两个 side cell，每个 side cell 恰有 4356 个 MIM 实例；
- 中间预留 30 µm 的未来布线走廊，并加入 28 个清楚标成 `PLAN_*` 的未连接引脚规划标记。

这仍然是**未布线的 floorplan**。它不是最终 CDAC 版图，不能据此声称 LVS、PEX 或 ADC 后仿真通过。

![完整差分 CDAC floorplan](artifacts/cdac_diff_floorplan.png)

引脚规划标记在完整视图里很小，下面是中间走廊的放大图。P、N 两侧各有 `TOP`、`B11…B0` 和 `DUMMY`；这些粉色方块是未来布线落点，不是已经接通的引脚。

![未连接 pin 规划走廊](artifacts/cdac_pin_corridor.png)

## 为什么没有继续使用 4 µm pitch

CSV 最初的 4 µm 只是面积估算。真实的 3 µm × 3 µm MIM PCell 包含接触和金属延伸，实际几何外框约为 **4.86 µm × 3.40 µm**。因此只看“3 µm 电容板”会低估所需间距。

本轮用真实 PCell 做了两单元边界扫描，并同时检查两个条件：

1. Magic DRC 数量必须为 0；
2. 提取出来的两个电容端子必须仍是两个独立节点，不能因为金属重叠而误短接。

第二条非常重要：例如 X 方向 4.8 µm 时，DRC 会显示 0，但相邻 M3 已经接触，提取结果显示端子被短在一起。也就是说，“DRC=0”本身并不足以证明 pitch 可用。

最终实测边界为：

| 方向 | 最后失败点 | 首个通过点／实际使用值 | 相对原 4 µm |
|---|---:|---:|---:|
| X | 5.99 µm | **6.00 µm** | +50.0% |
| Y | 4.53 µm | **4.54 µm** | +13.5% |

失败规则是 SKY130 Magic deck 的 `capm.11`：MIM 电容与无关 M3 的间距不足。完整探针结果保存在 `qualification.json` 的 `pitch_qualification.all_probes` 中，原始日志和每个两单元提取网表也一并保留。

## 面积结果

| 项目 | 当前结果 |
|---|---:|
| 单侧阵列外框 | 394.86 µm × 298.50 µm |
| 单侧外框面积 | 117,865.71 µm² = 0.117866 mm² |
| 差分顶层外框（含 30 µm 中间走廊） | 819.72 µm × 298.50 µm |
| 差分顶层外框面积 | 244,686.42 µm² = 0.244686 mm² |
| 两侧有效电容板面积 | 73,728 µm² |
| 有效板面积／两个 side 外框面积 | 31.28% |
| 单侧面积相对旧 264 µm × 264 µm 估算 | +69.11% |

这里报告的是当前 P/N 电容阵列 floorplan 面积，不是整颗芯片核心面积。参考开关、比较器、前端、偏置和数字控制都还没有计入。

## 关键文件

- `artifacts/cdac_diff_floorplan.gds`：可在 KLayout 中打开的差分顶层 GDS。
- `artifacts/cdac_diff_floorplan.mag`：Magic 顶层；引用两个 side cell。
- `artifacts/cdac_side_p.mag`、`artifacts/cdac_side_n.mag`：每侧 4356 个实例的层次化 Magic cell。
- `artifacts/placement_index.csv`：把每个实例绑定回 P/N、行列、`B11…B0/DUMMY/EDGE` 和新坐标。
- `artifacts/klayout_summary.json`：GDS 回读的层次、实例数、外框和 28 个规划标记。
- `qualification.json`：最终机器可读状态、全部检查、面积、工具/PDK 版本、哈希和明确限制。
- `artifacts/magic_floorplan.log`：P、N 和顶层 placement-only DRC 原始日志。
- `probe_artifacts/`、`probe_refine/`：pitch 扫描生成的两单元 MAG、提取网表和原始证据。

## 复现

当前项目使用固定的离线容器 `sky130-v2-resume-20260910`。在仓库根目录执行：

```bash
docker exec sky130-v2-resume-20260910 bash -lc \
  'python3 /repo/v2/physical/cdac_layout_20260911/qualify.py'
```

脚本会从原始 assignment CSV 开始，重新做 pitch 探针、生成全部 8712 个实例、运行 Magic placement-only DRC、用 KLayout 回读 GDS并生成两张预览图。成功时 `qualification.json` 的状态是 `SKY130_CDAC_PLACEMENT_FLOORPLAN_PASS`。

## 尚未完成，且不可省略

- 把每侧所有 top plate 接成低阻、对称网络；
- 把每个单位底板接到对应的 `B11…B0/DUMMY` 开关网络；
- 放置并连接参考开关、采样开关、比较器及参考供电；
- 完整 routed DRC；
- 用独立参考网表做 LVS；
- 寄生提取以及 reference droop、建立时间、线性、噪声和动态精度回归；
- 与前端、偏置、数字控制集成后的顶层验证；
- 最终 Cadence 原生版图与学校规则闭环。

所以本目录完成的是一个真实、可复核的**物理放置里程碑**，不是最终 CDAC 或完整 ADC 的物理签核。

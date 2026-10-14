# HANDOFF-M5（M4 → M5 交接快照）

> **用法**：新对话用 `/goal 读取 "plan/HANDOFF-M5.md" 继续完成任务`（绝对路径由用户侧拼）。
> **上游**：[00-README总览.md](00-README总览.md) · [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §三 M5 · [06-决策记录.md](06-决策记录.md) §二 E15/E22、§四 R2/R3
> **快照时间**：2026-10-14（M4 收尾，同日完成 M1→M2→M3→M4）
> **上一棒**：[HANDOFF-M4.md](HANDOFF-M4.md)（§六 M4 DoD 已全部完成）

---

## 一、当前进度（M4 已完成，本地等价校验通过）

| 项 | 状态 | 证据 |
|---|---|---|
| bench 三套件达标 + 退出码 0 | ✅ | 216/216（72 个有限边界）、42/42（21 组配对）、129/129（122 算例 + 7 误报对照）；门槛随 manifest 下发 |
| **探活实测留痕**（M4 验收门） | ✅ | 三套件各注入一次缺陷在**数据目录副本**实跑 `safefee bench`，全部实测变红（退出码 1）：`tiered_boundary` 210/216（区间重叠）、`synthetic_ledger` 114/129（费率改动）、`dual_version` 41/42（共享变体负单价）；记录进 [06-决策记录.md](06-决策记录.md) §二 **E23**（含注入方式与"非共享变体不进 dual_version 配对"的边界发现） |
| README 指标表终稿 | ✅ | 评测基准节升级为最终口径（用例数/门槛/实测值/退出码语义 + 探活记录表）；**M5 打包后指标不变即可冻结** |
| `diff --out` 对照报告导出 | ✅ | `ruleset/diff_report.py`：DiffReport → `ReportInput`（新增 `diff` 载荷 + "双版本差异对照"章节）复用 `report/` **单一渲染源**；产物 差异对照.md/差异对照.xlsx/evidence.json 三件；费率序列 `\|` 进 Markdown 表格自动转义（`render_markdown` 统一转义）；未启用章节显式写出沿用 |
| diff 导出测试 | ✅ | 7 项新测试（test_diff.py）：全条目映射、三件产物、无外链、**字节冻结**（同输入两次导出逐字节一致）、`\|` 转义、CLI 接线、同版无产物 |
| 测试 / 门禁 | ✅ | **186 项 py3.8+3.12 双绿**（179 + 7）；零字面量门禁 + 脱敏审计 OK；三生成器 `--check` 逐字节一致（8+4+130 份） |
| CI 实跑 | ⬜ | **本机无远端未跑 CI**——一律写"本地等价校验"，首推后据实补记（同 M0~M3 纪律） |

**遗留显式 pending**（不阻断计算路径）：安全生产法 2014/2021 修正日期、GB 12268 现行版本号（官方渠道不可取，clauses.json 登记）；2012 版进度门槛（无对应比例条款，显式 pending）。

---

## 二、M5 待办（桌面交付：PySide6 界面 + PyInstaller 打包 + 技术报告）

> **已就位**：GUI 骨架（`src/safefee/gui/` + `cli/cmd_gui.py`，缺依赖退出码 3，有分层测试 `test_gui_layering.py`）；编排层唯一入口 `engine/pipeline.py`（CLI 与 GUI 共用，**GUI 只消费引擎 API**——AST 守门在 M0 已建）；XLSX writer 为**自写最小 OOXML**（零第三方，`report/xlsx.py`）。

按序执行（每步有验收门）：

1. **GUI 界面完善**（PySide6 惰性导入）：档案表单 → calc/check/progress/diff 结果展示 + 报告导出按钮；**只消费 `pipeline` 公开函数，零政策数值零判定逻辑**（AST 三条守门：不 import rules/tiered/accrual 直接算）。
2. **行为等价三方对账**：同一输入 CLI stdout == 编排直调 == GUI 展示（对账测试，沿用 M2 形态）。
3. **PyInstaller 打包**：CLI + GUI 双 exe（onedir）；≥6 版本（本机 `py -3.12` 通道）；**随包数据白名单** `rules`/`truth`/`samples`（不整仓塞 `data/`）；**构建后断言**：冻结态可定位数据目录（`find_data_dir` frozen 分支）+ 各子命令自检过 + 报告可导出。
4. **中立目录验收**：双 exe 拷到无环境变量的中立目录，以 exe 目录为 CWD 自检（selfcheck/bench/calc/scan 全链）。
5. **演示素材可复现**：两次导出 sha256 一致（XLSX 字节冻结已有；MD 含真实时间按 E21 口径 `--fixed-time` 断言）。
6. **`docs/技术报告.md` 入仓**（缓议 C2：Markdown 优先，跳过也要显式留档）。

---

## 三、既定口径清单（**动了会打挂基准**，改前先对照 HANDOFF-M4 §三 全表 + 06 §六速查）

M4 新增/相关口径：

| 口径 | 当前定稿 | 改动影响 |
|---|---|---|
| **探活注入点（M4 新）** | tiered_boundary 注区间重叠（费率/单价打不红它）；dual_version 注**两版共享节点**负值（非共享变体不进配对） | 06 E23；探活复现 |
| **diff 报告导出（M4 新）** | DiffReport → ReportInput（diff 载荷）→ 单一渲染源；差异对照.md/差异对照.xlsx/evidence.json 三件；同版两年度提示且**不写产物**（退出码 0） | test_diff.py 7 项 |
| **Markdown 表格转义（M4 新）** | 单元格内 `\|` 统一转义（费率序列撑破表格） | render_markdown；全部表格产物 |
| **README 指标冻结（M4 新）** | 指标口径 = 用例数/门槛/实测值/退出码语义；M5 打包后指标不变即冻结 | README 评测基准节 |

---

## 四、本机环境坑（实测过，沿用 M1~M3）

- `py -0p` 有 3.8.8 与 3.12；默认用 `py -3.12 -X utf8` 跑（中文控制台）。
- **Git Bash 里 `python` 命令 exit 49 无输出——一律 `py -3.12`（或 `py -3.8`）**；heredoc 用 `py -3.12 -X utf8 - << 'EOF'`。
- venv 段落一律 `python -m pip`；`PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏——出怪错先清 `__pycache__`）。
- 临时文件用工作区相对路径；子进程显式 `encoding="utf-8"`；生成器一律 `write_bytes`。
- 显示层偶发污染（Read 回读）：改文件优先整文件重写或断言计数替换。
- **`--data-dir` 是全局参数，须置于子命令前**（`safefee --data-dir X bench` ✅ / `safefee bench --data-dir X` ❌ exit 2）——批量脚本里用 `SAFEFEE_DATA_DIR` 环境变量更稳（M4 探活实测）。
- 探活/对账类实验**在数据目录副本上做**（copytree + 重刷副本 manifest 指纹），原库零接触；副本 JSON 用普通 `json.load`（不带 parse_float=Decimal，Decimal 不可序列化）。
- **PyInstaller**：构建固定在 `py -3.12` 通道（≥6 版本）；随包数据白名单见 §二.3。
- **gov.cn 抓取**：`curl -sSL` 可直连 gongbao/zhengceku 静态页；flk.npc.gov.cn / npc.gov.cn / mem.gov.cn 不可 curl。

## 五、关键命令速查

```bash
# 生成冻结产物 + 守门
py -3.12 -X utf8 tools/gen_rulesets.py --check
py -3.12 -X utf8 tools/gen_samples.py  --check
py -3.12 -X utf8 tools/gen_synthetic.py --check   # 含陈旧文件检测

# 两个扫描器（含阳性对照）
py -3.12 -X utf8 tools/scan_policy_literals.py --selftest && py -3.12 -X utf8 tools/scan_policy_literals.py
py -3.12 -X utf8 tools/dessensitize_audit.py --selftest && py -3.12 -X utf8 tools/dessensitize_audit.py

# 测试（双解释器；裸 python 不可用）
PYTHONPATH=src py -3.12 -X utf8 -m pytest -q     # 186 项
PYTHONPATH=src py -3.8  -X utf8 -m pytest -q

# CLI 冒烟
PYTHONPATH=src py -3.12 -X utf8 -m safefee version && PYTHONPATH=src py -3.12 -X utf8 -m safefee selfcheck && PYTHONPATH=src py -3.12 -X utf8 -m safefee bench
PYTHONPATH=src py -3.12 -X utf8 -m safefee calc data/samples/archive-coal.json
PYTHONPATH=src py -3.12 -X utf8 -m safefee diff --from-year 2020 --to-year 2024 --out <报告目录>
PYTHONPATH=src py -3.12 -X utf8 -m safefee scan <台账目录> --out <输出目录> --report

# M5 打包（待做）
py -3.12 -X utf8 -m PyInstaller <CLI spec>       # 双 exe onedir；≥6 通道
```

## 六、M5 DoD checklist（执行时逐项打勾）

- [ ] GUI 只消费引擎 API（AST 三条守门复跑）；零政策数值零判定逻辑
- [ ] 行为等价三方对账（CLI stdout == 编排直调 == GUI 展示）
- [ ] 双 exe（CLI + GUI）PyInstaller ≥6 onedir 构建成功；随包数据白名单（rules/truth/samples）
- [ ] 构建后断言：冻结态数据目录定位 + 各子命令自检 + 报告可导出
- [ ] 中立目录验收：清环境变量 + exe 目录为 CWD，全链自检过
- [ ] 演示素材可复现（两次 sha256 一致；按 E21 口径）
- [ ] `docs/技术报告.md` 入仓（缓议 C2 定夺：跳过也要显式留档）
- [ ] 全链本地等价校验绿（186+ 项测试双解释器；基准三套件达标不回退）
- [ ] 里程碑状态回写（plan/00 + 05 + 06 + README + HANDOFF-M6 落盘）

## 七、禁止事项（沿用 M1~M3 + M4 教训）

- **不得手改** `data/rules/**` 与 `data/truth/**`（生成器唯一写入者）。
- **不得**把未核对数值落库或写进代码；`status=pending` 必须配 `value: null`。
- **不得**写"CI 绿"（本机无远端）；只写"本地等价校验"。
- **不得**在公开文档提其余项目业务领域（品牌隔离）。
- **不得**在 GUI 层写判定逻辑或政策数值（AST 守门）——GUI 只渲染结果。
- **不得**把 85% 阈值等政策参数写死在引擎（数据下发）；不得在 `tools/gen_synthetic.py` 复制政策字面量。
- **不得**让 `scan` 因核查结论（含不符合）或失败件改退出码（M3 两层语义锁进测试）。
- **不得**用费率/单价类缺陷探活 `tiered_boundary`；dual_version 探活注入点必须选两版共享节点（06 E23）。
- **不得**让 Markdown 表格单元格裸出 `|`（render_markdown 已统一转义）。
- **不得**让 GUI 缺 PySide6 时崩溃——惰性导入 + 退出码 3（M0 契约，测试锁定）。

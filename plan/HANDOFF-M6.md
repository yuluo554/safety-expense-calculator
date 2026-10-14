# HANDOFF-M6（M5 → M6 交接快照）

> **用法**：新对话用 `/goal 读取 "plan/HANDOFF-M6.md" 继续完成任务`（绝对路径由用户侧拼）。
> **上游**：[00-README总览.md](00-README总览.md) · [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §三 M6 · [06-决策记录.md](06-决策记录.md) §四/§五
> **快照时间**：2026-10-14（M5 收尾，同日完成 M1→M2→M3→M4→M5）
> **上一棒**：[HANDOFF-M5.md](HANDOFF-M5.md)（§六 M5 DoD 已全部完成）

---

## 一、当前进度（M5 已完成，本地等价校验通过）

| 项 | 状态 | 证据 |
|---|---|---|
| GUI 只消费引擎 API（AST 三条守门复跑） | ✅ | 四页签（计提/核查/进度/对照）全部动作走 `engine.pipeline` 公开函数；`gui/widgets.py` 是 Qt 唯一所在，`gui/render.py` 无 Qt 依赖；AST 三守门（不 import 领域层/无算术 BinOp/无政策数值）复跑绿 + 守门可证伪测试在库 |
| 行为等价三方对账 | ✅ | CLI stdout == 编排直调 `format_*` == GUI 显示块**逐行相等**（构造性同源，06 E24）；`tests/test_gui_m5.py` 16 项新测试 |
| 双 exe PyInstaller ≥6 onedir | ✅ | `tools/safefee_cli.spec` + `tools/safefee_gui.spec` 入仓；PyInstaller 6.22.3 @ py3.12 通道；随包数据白名单 `rules/truth/samples` → `_internal/data`；GUI 包含 `src/safefee/gui_app.py`（窗口态入口） |
| 构建后断言 | ✅ | `tools/verify_frozen.py` 八项断言全过（selfcheck 数据目录命中 dist + bench 三套件达标 216/216、42/42、129/129 + calc/check/progress/diff 全链 + calc --out / diff --out 三件产物）；退出码双向验证（好包 0 / 坏路径 1）——期间抓出并修复 `_fail` 返回 False 的**假绿 bug** |
| 中立目录验收 | ✅ | 双 exe 拷至无 `SAFEFEE_DATA_DIR` 的临时目录、exe 目录为 CWD：selfcheck/bench/calc/check/diff/报告导出全链过；GUI exe 实机启动验证（进程存活后正常终止） |
| 演示素材可复现（E21 口径） | ✅ | `--fixed-time` 下 calc 报告两次导出 sha256 逐字节一致（三件全一致，实测留痕）；差异对照报告**默认**即字节冻结；`calc/check/progress --fixed-time` 全局参数接线（06 E26） |
| `docs/技术报告.md` 入仓 | ✅ | 缓议 C2 定夺为 **Markdown 优先交付**（架构/决策/门禁/打包/边界七章）；README 补「桌面交付（M5）」节 |
| 测试 / 门禁 | ✅ | **202 项 py3.8+3.12 双绿**（186 + 16）；零字面量门禁 + 脱敏审计 OK；三生成器 `--check` 逐字节一致（8+4+130 份）；基准三套件不回退 |
| CI 实跑 | ⬜ | **本机无远端未跑 CI**——一律写"本地等价校验"，首推后据实补记（同 M0~M4 纪律） |

**M5 实测环境坑（新增两条，06 E25）**：
- PyInstaller `SPECPATH` = spec 文件所在目录（`tools/`），仓库根取其父目录（spec 内 assert 自校验）。
- 冻结态 exe 管道输出按中文 Windows ANSI 码页（GBK）——`PYTHONUTF8=1` 对冻结 exe 不生效；验收脚本解码 UTF-8 优先、GBK 回退。

**遗留显式 pending**（不阻断计算路径）：安全生产法 2014/2021 修正日期、GB 12268 现行版本号（官方渠道不可取，clauses.json 登记）；2012 版进度门槛（无对应比例条款，显式 pending）。

---

## 二、M6 待办（脱敏发布 GitHub + Release（exe）+ 收尾固化）

> **已就位**：脱敏审计器 `tools/dessensitize_audit.py`（selftest + 三模式）；合成企业白名单（虚构名称 + `90000000…SYN` 号段）；`data/**/_private/` 已 gitignore；CI workflow 四矩阵已接线未跑。

按序执行（每步有验收门）：

1. **脱敏四步留痕**：①历史扫描（`git log -p` 全量过一遍敏感词）；②产物本体扫描（dist/ 内文件名+字符串抽查）；③邮箱检查（`git log` 作者邮箱 == 署名 yuluo554）；④品牌隔离复查（公开文档不提其余项目业务领域）。四步输出留档进 plan/06 或独立 `docs/发布检查单.md`。
2. **干净环境按 README 逐字跑通**：venv 全新建立 → README 快速开始段落逐字执行 → 快速开始/桌面交付两节命令全部按退出码表过。
3. **首推 GitHub**（`yuluo554/safety-expense-calculator`，纯净名）：push 后**据实补记 CI 首跑结果**（四矩阵；此前所有文档只写"本地等价校验"，首跑绿后方可补写"CI 绿"）。
4. **Release（exe）**：双 exe 打包 zip（CLI + GUI 两个 onedir 目录）附 Release；tag 命名与 release 说明**须经用户确认**后才推送。
5. **缓议项清零**：06 §五缓议项逐条查证现状 → 定夺或显式顺延（C2 技术报告格式已于 M5 定夺为 Markdown；逐条核对 plan/06 §五清单）。
6. **收尾固化**：README 状态行改"已发布"；plan/00/05/06 状态回写；HANDOFF-M6 §六打勾。

---

## 三、既定口径清单（**动了会打挂基准**，改前先对照 HANDOFF-M5 §三 全表 + 06 §六速查）

M5 新增/相关口径：

| 口径 | 当前定稿 | 改动影响 |
|---|---|---|
| **GUI 展示同源（M5 新）** | CLI stdout 与 GUI 显示块共用 `pipeline.format_*` 四个纯函数（06 E24） | test_gui_m5 三方对账四项 |
| **报告时间语义落地（M5 新）** | `calc/check/progress --fixed-time` 全局参数；报告默认含真实时间，复现断言走 fixed-time；diff 报告默认字节冻结（06 E26） | test_gui_m5 复现四项 |
| **冻结态数据定位（M5 新）** | 白名单 `rules/truth/samples` → `_internal/data`；`find_data_dir` frozen 分支优先级不变（06 E25） | verify_frozen + test_data_paths |
| **GUI 缺依赖契约（不变）** | 源码态缺 PySide6 → 退出码 3（import 桩测试；真实界面走 offscreen 冒烟，不进事件循环） | test_cli gui 两项 + test_gui_m5 |
| **README 指标冻结** | M4 口径不变；打包后实测值未回退（216/216、42/42、129/129 冻结态复测一致） | README 评测基准节 |

---

## 四、本机环境坑（实测过，沿用 M1~M5）

- `py -0p` 有 3.8.8 与 3.12；默认用 `py -3.12 -X utf8` 跑（中文控制台）。
- **Git Bash 里 `python` 命令 exit 49 无输出——一律 `py -3.12`（或 `py -3.8`）**；heredoc 用 `py -3.12 -X utf8 - << 'EOF'`。
- venv 段落一律 `python -m pip`；`PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏——出怪错先清 `__pycache__`）。
- 临时文件用工作区相对路径；子进程显式 `encoding="utf-8"`；生成器一律 `write_bytes`。
- 显示层偶发污染（Read 回读）：改文件优先整文件重写或断言计数替换。
- **`--data-dir` 是全局参数，须置于子命令前**——批量脚本里用 `SAFEFEE_DATA_DIR` 环境变量更稳。
- 探活/对账类实验**在数据目录副本上做**（copytree + 重刷副本 manifest 指纹），原库零接触。
- **PyInstaller**：构建固定 `py -3.12` 通道；spec 内 `SPECPATH` = tools/ 自身（取父目录为仓库根）；**冻结 exe 管道输出是 GBK**（PYTHONUTF8 不生效），验收解码须 GBK 回退。
- **pytest 全量本机约 1~2 分钟**；`safefee gui` 直跑会进 Qt 事件循环阻塞——测试一律 offscreen + 不调 `app.exec()`（或桩住）。
- **gov.cn 抓取**：`curl -sSL` 可直连 gongbao/zhengceku 静态页；flk.npc.gov.cn / npc.gov.cn / mem.gov.cn 不可 curl。

## 五、关键命令速查

```bash
# 生成冻结产物 + 守门
py -3.12 -X utf8 tools/gen_rulesets.py --check
py -3.12 -X utf8 tools/gen_samples.py  --check
py -3.12 -X utf8 tools/gen_synthetic.py --check

# 两个扫描器（含阳性对照）
py -3.12 -X utf8 tools/scan_policy_literals.py --selftest && py -3.12 -X utf8 tools/scan_policy_literals.py
py -3.12 -X utf8 tools/dessensitize_audit.py --selftest && py -3.12 -X utf8 tools/dessensitize_audit.py

# 测试（双解释器；裸 python 不可用）
PYTHONPATH=src py -3.12 -X utf8 -m pytest -q     # 202 项
PYTHONPATH=src py -3.8  -X utf8 -m pytest -q

# GUI 冒烟（offscreen）
QT_QPA_PLATFORM=offscreen PYTHONPATH=src py -3.12 -X utf8 -m pytest tests/test_gui_m5.py tests/test_gui_layering.py -q

# 打包 + 冻结态验收
py -3.12 -X utf8 -m PyInstaller tools/safefee_cli.spec --distpath dist/m5 --workpath build/m5 --noconfirm
py -3.12 -X utf8 -m PyInstaller tools/safefee_gui.spec --distpath dist/m5 --workpath build/m5 --noconfirm
py -3.12 -X utf8 tools/verify_frozen.py --dist dist/m5/safefee-cli

# CLI 冒烟（源码态）
PYTHONPATH=src py -3.12 -X utf8 -m safefee version && PYTHONPATH=src py -3.12 -X utf8 -m safefee selfcheck && PYTHONPATH=src py -3.12 -X utf8 -m safefee bench
PYTHONPATH=src py -3.12 -X utf8 -m safefee calc data/samples/archive-coal.json --out <报告目录> --fixed-time 2026-10-14T00:00:00
PYTHONPATH=src py -3.12 -X utf8 -m safefee diff --from-year 2020 --to-year 2024 --out <报告目录>
```

## 六、M6 DoD checklist（执行时逐项打勾）

- [ ] 脱敏四步留痕（历史扫描 + 产物本体扫描 + 邮箱检查 + 品牌隔离复查）
- [ ] 干净环境按 README 逐字跑通（venv 全新 → 快速开始全命令）
- [ ] 首推 GitHub + CI 首跑四矩阵结果据实补记（此前文档只写"本地等价校验"）
- [ ] Release（exe）zip 附双 onedir；tag/release 说明经用户确认
- [ ] 缓议项清零（06 §五逐条定夺或显式顺延）
- [ ] 里程碑状态回写（plan/00 + 05 + 06 + README 终稿）
- [ ] 全链本地等价校验绿（202 项测试双解释器；基准三套件达标不回退）

## 七、禁止事项（沿用 M1~M5）

- **不得手改** `data/rules/**` 与 `data/truth/**`（生成器唯一写入者）。
- **不得**把未核对数值落库或写进代码；`status=pending` 必须配 `value: null`。
- **不得**写"CI 绿"（本机无远端；首推 CI 实跑绿之前只写"本地等价校验"）。
- **不得**在公开文档提其余项目业务领域（品牌隔离）。
- **不得**在 GUI 层写判定逻辑或政策数值（AST 守门）——GUI 只渲染结果。
- **不得**把 85% 阈值等政策参数写死在引擎（数据下发）；不得在 `tools/gen_synthetic.py` 复制政策字面量。
- **不得**让 `scan` 因核查结论（含不符合）或失败件改退出码（M3 两层语义锁进测试）。
- **不得**用费率/单价类缺陷探活 `tiered_boundary`；dual_version 探活注入点必须选两版共享节点（06 E23）。
- **不得**让 Markdown 表格单元格裸出 `|`（render_markdown 已统一转义）。
- **不得**让 GUI 缺 PySide6 时崩溃——惰性导入 + 退出码 3（M0 契约，测试锁定）。
- **不得**未经用户确认推 tag / 发 Release（M6 新增；对外发布动作）。

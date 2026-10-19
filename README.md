# safety-expense-calculator

企业安全生产费用提取与使用合规计算工作台 —— 以《企业安全生产费用提取和使用管理办法》（**财资〔2022〕136号**）为规则源，把**十二行业计提标准 + 超额累退分段计算 + 双版本对照（2022 版 vs 2012 版）+ 支出范围合规核查 + 批量台账对账 + 报告导出**做成**逐笔挂条款依据、可复现、留指纹**的本地工具（桌面 exe + CLI 双形态）。

**全本地处理、零上传**：企业台账可能含经营敏感信息，工具默认不联网、不做任何数据外发。

> 状态：✅ **已发布（2026-10-14，M6 收尾）**——M0~M5 全链完成（计提引擎/核查对账/基准/桌面交付，详见下方里程碑表）；M6 完成脱敏发布：GitHub 首推 + **CI 双矩阵全绿**（ubuntu/windows × py3.12，首跑暴露并修复 GUI 冒烟测试的 PySide6 依赖问题，见 plan/06 E27）+ Release（exe）+ [发布检查单](docs/发布检查单.md) 留档。214 项测试（Ubuntu/Windows × py3.12 双绿；无 PySide6 环境 210 passed + 4 skipped）+ CI 绿。**2026-10-19 二次迭代**（解释器底线抬至 3.12、脱敏历史扫描入门禁、文档计数与元数据对齐、规则包增机读复核锚）推送后**双矩阵复跑全绿**（run 39275075515；决策与实测见 plan/06 E29~E33）。

---

## 它解决什么问题

| 痛点 | 本工具的能力 |
|---|---|
| 我这企业该按什么标准提？产量、营业收入还是工程造价？ | 计提依据选择判定（含跨行业、净额口径、从高提取规则） |
| 超额累退的"分段"到底怎么算才对？ | 逐段分解（依据量 / 费率 / 段内金额 / 依据条款），分段边界显式处理 |
| 2022 版和 2012 版数值差在哪？旧台账能不能用新标准重算？ | 双版本规则集 + 差异对照 + 按年度锚定版本（杜绝口径失真） |
| 这笔支出到底算不算安全生产费用能列支的？ | 支出明细逐笔映射到办法"应当用于以下支出"条目，四态判定挂条款 |
| 去年到底提够没有？ | 使用进度门槛判定（不足规定比例须披露并书面说明） |
| 台账以千条计，逐笔点开不现实 | 批量扫描 + 失败件隔离 |
| 整改是循环的，"这轮比上轮好了没" | 跨年对账：新增异常 / 已修复 / 持续异常 |
| 结论要能交给审计/存档 | 报告导出（Markdown + XLSX）+ 台账 sha256 指纹 |

## 规则库版本化与 status 门控（本项目的核心纪律）

规则库按 **`依据文件 × 版本`** 组织（`data/rules/`），计提标准编码为可执行规则（JSON）。每条挂文号/条款号与 `status`：

- `verified` —— 已逐条挂原文核对，**可进入计算路径**；
- `pending` —— 待核对，**绝不参与任何计算或判定**。

门控**按计算路径分作用域**（`calc` / `check` / `progress`），互不误伤：算 coal 时不被 machinery 的 pending 拖累。**未挂原文核对的条目不得落库生效**——这是"不编造标准值、不输出假结论"的工程落点。

锚定年度即锚定规则版本：`财企〔2012〕16号` 与 `财资〔2022〕136号` 是两套独立规则集，切换即切口径。

## 依据锚点（基准日 2026-10-14 核验）

| 依据 | 编号 | 状态 |
|---|---|---|
| 企业安全生产费用提取和使用管理办法 | **财资〔2022〕136号** | ✅ 成文 2022-11-21 / 发布 2022-12-14 / **自印发之日起施行**；第六十九条废止财企〔2012〕16号（原文核对）；计提标准已逐条核对落值 |
| 同上（旧版，历史年度对照） | **财企〔2012〕16号** | ✅ 2012-02-14 发布、五章四十条；煤炭/建设工程/危险品已逐条核对落值 |
| 应急管理部令第 8 号（修改《煤矿安全规程》） | 8 号令 | ✅ 2022-01-06 公布、自 2022-04-01 施行（公报原文核对） |
| 中华人民共和国安全生产法 | 主席令第七十号（2002） | ✅ 2002 原始公布核对；⬜ 2014/2021 修正日期显式留 pending（官方原文未取到，不写入） |

> 依据快照与逐条核对记录：[data/README.md](data/README.md) §二、[data/knowledge/clauses.json](data/knowledge/clauses.json)。

> **基准日核验**：财资〔2022〕136号**未见替代/作废/延期公告，当年无换版**；2012 版已于 2022 年废止（非当年事件）。

> **复核锚（机读）**：规则包清单（`data/rules/manifest.json`）登记**复核周期**与**下次复核日**，`safefee selfcheck` 会打印它并在逾期时提示重新核对官方原文——费率/条款会换版，这个锚点就是"什么时候该回来复核"的落点。

## 快速开始

要求 Python 3.12+（核心功能无第三方依赖）。

```bash
python -m venv .venv
# Windows(Git Bash): source .venv/Scripts/activate    Linux/macOS: source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

> **Windows 提示**：venv 段落一律用 `python -m pip`（激活后 `python` 才指向 venv）——
> 用 `py -m pip` 会绕过 venv 装到系统 Python。

> **两个可选 extra**（核心层零第三方依赖，按需装）：
> 桌面界面 `safefee gui` 需 `python -m pip install -e ".[gui]"`（PySide6；缺依赖退出码 3）；
> 读入 XLSX 台账需 `python -m pip install -e ".[xlsx]"`（openpyxl；缺依赖按 CSV 路径降级）。
> `.[dev]` 不含这两个 extra，故无 GUI 环境下 4 项界面冒烟测试会跳过（见下方测试数口径）。

生成冻结产物（规则包 / 演示夹具 / 真值库骨架）并校验"再生成逐字节一致"：

```bash
python tools/gen_rulesets.py            # 生成规则包 → data/rules/
python tools/gen_samples.py             # 生成演示夹具 → data/samples/
python tools/gen_synthetic.py           # 生成真值库骨架 → data/truth/
python tools/gen_rulesets.py --check    # 应输出 FROZEN_RULESETS_OK
```

跑起来：

```bash
safefee selfcheck                        # 数据目录定位 + 规则集加载 + 门控计数
safefee rulesets                          # 规则集清单与状态
safefee bench                             # 内置评测基准（三类套件）
safefee calc data/samples/archive-coal.json    # 计提计算（已核对行业输出金额，退出码 0）
safefee calc data/samples/archive-coal.json --out <报告目录> --fixed-time 2026-10-14T00:00:00
                                               # 计提 + 报告导出（MD/XLSX/evidence；--fixed-time 为复现断言用）
safefee check data/samples/ledger-demo.csv --archive data/samples/archive-coal.json
safefee progress data/samples/archive-coal.json --accrued 100000 --used 40000
safefee diff --from-year 2020 --to-year 2024   # 双版本差异对照
safefee diff --from-year 2020 --to-year 2024 --out <报告目录>
                                               # 对照报告导出（MD/XLSX/evidence 三件）
safefee scan <台账目录> --out <报告目录>        # 批量扫描（逐笔四态核查）+ 跨年对账
safefee scan <台账目录> --out <报告目录> --report --baseline <上轮scan-result.json>
                                               # 结果直接驱动报告导出 + 两轮对账
safefee gui                                    # 桌面界面（M5 交付；缺依赖退出码 3）
```

## 桌面交付（M5）

**双形态**：源码态 `safefee gui`（惰性导入 PySide6，缺依赖退出码 3）+ 发行包双 exe。

**桌面界面**（四页签，全部动作走编排层 `engine/pipeline.py`，展示文本与 CLI stdout 同一实现源）：

| 页签 | 输入 | 输出 |
|---|---|---|
| 计提计算 | 企业档案表单（编号/行业/年度/依据量/变体） | 机制/公式/条款/逐段明细/依据选择判定/提示 + 报告导出（MD/XLSX/evidence） |
| 支出核查 | 档案 JSON 路径 + 台账 CSV 路径 | 四态逐笔结论 + 红线清单 |
| 使用进度 | 档案路径 + 应计提/实际使用额 | 门槛比例 + 披露义务 + 条款依据 |
| 版本对照 | 起始/目标年度 | 差异计数 + 差异明细 + 对照报告导出 |

**打包与验收**（构建固定 `py -3.12` 通道，PyInstaller ≥6 onedir）：

```bash
py -3.12 -X utf8 -m PyInstaller tools/safefee_cli.spec --distpath dist/m5 --workpath build/m5 --noconfirm
py -3.12 -X utf8 -m PyInstaller tools/safefee_gui.spec --distpath dist/m5 --workpath build/m5 --noconfirm
py -3.12 -X utf8 tools/verify_frozen.py --dist dist/m5/safefee-cli   # 退出码 0 = 全部断言过
```

- **随包数据白名单**：`rules` / `truth` / `samples` 三目录进 `_internal/data/`（核对底稿不进发行包）；冻结态数据目录定位优先级见 `src/safefee/data_paths.py`。
- **构建后断言 + 中立目录验收**（M5 实测留痕，2026-10-14）：`verify_frozen.py` 断言 8 项——selfcheck（数据目录命中 `_internal/data`）、bench 三套件达标（216/216、42/42、129/129）、calc/check/progress/diff 全链、calc --out 与 diff --out 三件产物；双 exe 拷至无 `SAFEFEE_DATA_DIR` 的中立目录、以 exe 目录为 CWD 实测通过；GUI exe 实机启动验证。
- **演示素材可复现**（E21 口径）：报告默认含真实时间；`--fixed-time` 下同输入两次导出，MD/XLSX/evidence **sha256 逐字节一致**（测试锁定 + 实测留痕）；差异对照报告默认即字节冻结（对照报告不含生成时间）。

> **数据文件 ≠ 命令输入**：演示夹具是可直接喂给命令的裸档案/台账
> （`data/samples/archive-*.json`、`data/samples/ledger-demo.csv`），
> 由 `tools/gen_samples.py` 产出并纳入"再生成逐字节一致"守门。

## 评测基准（最终指标口径，M4 冻结）

`safefee bench` 三类套件，**零第三方依赖、零外网、单次 <1 秒**。指标口径：**门槛随 `data/rules/manifest.json` 下发（门槛是数据不是代码，缺失即退出码 2）；实测值 = 通过用例数 / 总用例数；退出码 0 = 全部可评估套件达标，1 = 任一可评估套件未达标，2 = 门槛缺失/输入/坐标错误**。用例数为 0 的套件标为**未评估**（不声称达标也不判未达标，不阻断退出码）。

| 套件 | 类型 | 内容 | 用例数（M4 实测） | 门槛 | 实测 | 退出码 |
|---|---|---|---|---|---|---|
| `tiered_boundary` | **规则驱动** | 从规则表推导全部 72 个有限分段点，做 `{p-0.01, p, p+0.01}` 邻域枚举断言段归属与逐段金额自洽（**不读真值库**；按独立阶梯枚举） | 216 | `min_pass_ratio: 1.0` | 216/216 | 0 |
| `dual_version` | 规则驱动 | 两版规则对同一对象各算期望值（21 组配对），断言版本切换不串口径 | 42 | `min_consistency: 1.0` | 42/42 | 0 |
| `synthetic_ledger` | **样本驱动** | 合成台账真值库全量重算对账（122 算例 + 7 误报对照；期望值由生成器**独立计算路径**产出，双重记账） | 129 | `min_truth_match: 1.0` | 129/129 | 0 |

**可证伪探活（M4 实测留痕，2026-10-14）**：对每套件在**数据目录副本**上注入缺陷实跑 `safefee bench`，基准必须变红（退出码 1）——记录见 [plan/06-决策记录.md](plan/06-决策记录.md) §二 E23：

| 探活 | 注入缺陷 | 实测结果 |
|---|---|---|
| `tiered_boundary` | 烟花爆竹第二段下界 10000000→5000000（区间重叠） | 210/216 红（"段内依据量之和 ≠ 依据量"抓到 6 例） |
| `synthetic_ledger` | 危险品首段费率 0.045→0.0449（结构自洽不破坏） | 114/129 红（9 个真值算例金额不符） |
| `dual_version` | 两版共享变体（煤炭其他井下）单价 15→−5 | 41/42 红（"金额为负"断言抓到） |

**分段边界口径**：段区间 `[lower, upper)`，**恰好等于分段点归下一段**；金额逐段量化到分后求和（不是"总额乘单一费率"）。

## 项目结构与纪律

```
src/safefee/           核心包（零第三方依赖）
  rules/              规则包加载 + manifest + status 门控（分作用域）
  tiered/             超额累退分段计算器（逐段可溯）
  accrual/            三类计提机制 + 依据选择判定
  ruleset/            年度→版本锚定 + 双版本差异对照
  spending/           支出核查（四态）+ 使用进度门槛
  batch/              批量扫描（失败隔离）+ 跨年对账（四集合）
  report/             单一渲染源 → Markdown / 自写最小 XLSX writer
  engine/pipeline.py  编排层（CLI 与 GUI 唯一入口）
  gui/                PySide6 界面（只消费编排层；AST 三条守门）
  cli/                子命令（退出码 0/1/2/3 契约）
tools/                生成器、扫描器与打包 spec / 冻结态验收
tests/                214 项（py3.12；无 PySide6 环境 210 passed + 4 skipped）
```

工程纪律（逐条有测试守门）：规则包**禁手改**（生成器唯一写入者，`--check` 逐字节一致）；**零政策字面量门禁**（数值只能来自规则包）；**溯源完整性**（导出前断言，不留半溯源）；报告**无外链**且 XLSX **逐字节可复现**；**字节冻结两层**（文本 EOL + zip 容器）；**编码三道加固**；**退出码三语义**锁进测试。

## 里程碑

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 计划 00–06 定稿 + 可运行骨架（规则加载/门控/计提骨架/CLI/基准/测试/CI） | ✅ 本地等价校验通过 |
| M1 | 数据先行：十二节计提规则逐条挂原文核对 + 双版本规则包 + 合成台账真值库 | ✅ 本地等价校验通过（四节落值 + 真值库 29 例 + 基准三套件全达标；详见 HANDOFF-M1 §DoD） |
| M2 | 计提引擎：三类机制 + 超额累退分段 + 依据选择判定 | ✅ 本地等价校验通过（十二节全落值可算 + 依据判定接入 + 真值库 122 例 + 基准三套件全达标；详见 HANDOFF-M2 §DoD） |
| M3 | 支出核查与对账：四态判定 + 批量扫描 + 跨年对账 + 报告/证据链 | ✅ 本地等价校验通过（spending 扩至十二节 + scan 接真四态 + 四集合对账 + scan 驱动报告 + 指纹防篡改；详见 HANDOFF-M3 §DoD） |
| M4 | 基准：三类套件达标，指标进 README；双版本差异对照 | ✅ 本地等价校验通过（三套件 216/216、42/42、129/129 退出码 0 + 探活实测变红留痕（plan/06 E23）+ README 指标表终稿 + `diff --out` 对照报告导出（MD/XLSX/evidence，无外链 + 字节冻结）） |
| M5 | 桌面交付：PySide6 界面 + PyInstaller 打包 + 报告导出 + 技术报告 | ✅ 本地等价校验通过（GUI 四页签只消费编排层 API（AST 三条守门 + 三方对账 16 项新测试）+ 双 exe onedir 构建 + 随包数据白名单 + 构建后断言/中立目录验收全链实测 + `--fixed-time` 复现 sha256 一致 + [技术报告](docs/技术报告.md) 入仓；214 项测试全绿） |
| M6 | 脱敏发布 GitHub + Release（exe）+ 收尾固化 | ✅（2026-10-14：脱敏四步留痕（[发布检查单](docs/发布检查单.md)）+ 干净 venv 按 README 逐字跑通 + 首推 GitHub + **CI 首跑修复后四矩阵全绿**（E27；矩阵已于 2026-10-19 收缩为 ubuntu/windows × py3.12 双矩阵，见 plan/06 E29）+ Release（exe）zip 中立目录复验 + 缓议项 C1~C4 清零） |

## 限制与免责

- **计提范围**：财资〔2022〕136号**十二节计提标准全部落值可算**（`calc` 退出码 0），2012 版九类同步落值用于历史对照；**无 `deferred` 行业**。支出范围核查（M3 起）覆盖**十二节全部行业**（spending 条目逐条挂原文核对；无条目命中 = `未评估`，绝不虚报`符合`）；使用进度核查为 2022 版第五十一条（60% 门槛；2012 版无对应条款显式 pending）。
- **依据选择判定**：多灾害并存矿井从高提取（第七条）、跨行业经营（第五十二条）、承揽承运净额口径（第五十三条，阈值 85% 来自规则包）——判定结论进结果与报告；**档案属性缺失（如矿井 `mine_type`）→ 退出码 2，绝不静默取 0/1**。
- 本工具输出为**基于条款的计提测算与合规检查发现**，不构成会计/审计/法律意见；正式结论以主管财政部门与应急管理部门口径、执业机构意见为准。
- 规则条目核对状态以规则库 `status` 为准；**`pending` 条目不参与计算**。
- 演示与基准一律使用**合成企业台账**（虚构名称 + `90000000…SYN` 测试号段），不含任何真实企业数据。
- **不做**：会计记账/凭证生成；税务处理与税前扣除判定；审计意见；监管申报接口；真实企业数据采集。

## 已知环境问题

- 本机多 Python 版本时，构建/打包固定在装了较新 PyInstaller 的通道（本机 = `py -3.12`）。
- 中文控制台输出由入口 `_ensure_utf8_stdio()` 按编码探针加固；CI 侧另设 `PYTHONUTF8=1`。
- CI：`ubuntu/windows × py3.12` 双矩阵——**2026-10-14 起实跑并全绿**（首跑修复记录见 [plan/06](plan/06-决策记录.md) E27）；解释器底线于 2026-10-19 抬升至 **3.12**（DEC1/理由全文见 plan/06 E29）。

## 许可

MIT，见 [LICENSE](LICENSE)。

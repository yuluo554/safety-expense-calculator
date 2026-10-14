# HANDOFF-M4（M3 → M4 交接快照）

> **用法**：新对话用 `/goal 读取 "plan/HANDOFF-M4.md" 继续完成任务`（绝对路径由用户侧拼）。
> **上游**：[00-README总览.md](00-README总览.md) · [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §三 · [06-决策记录.md](06-决策记录.md) §六
> **快照时间**：2026-10-14（M3 收尾，同日完成 M1→M2→M3）
> **上一棒**：[HANDOFF-M3.md](HANDOFF-M3.md)（§二 M3 待办已全部完成）

---

## 一、当前进度（M3 已完成，本地等价校验通过）

| 项 | 状态 | 证据 |
|---|---|---|
| spending 条目扩至十二节 | ✅ | 2022 版 **41 条**（十二节各 2~4 条允许 + 第四条第三项红线）、2012 版 **30 条**（九类各 2~3 条允许 + 第二十七条红线）——各节"应当用于以下支出"条款（136 号第 8/12/15/19/22/25/28/31/34/37/41/44 条；2012 版第 17~25 条）要点逐条对原文核对；`gen_rulesets.py --check` 逐字节一致 |
| checker 覆盖十二行业 | ✅ | `IN_SCOPE_INDUSTRIES` 扩至 2022 版十二节；四态语义不虚高（无条目命中=`未评估`，绝不虚报`符合`）保留并有测试 |
| scan 接真四态核查 | ✅ | `cmd_scan._check_one`：台账 CSV 7 列（enterprise_id/year/industry_id/item_key/subject/summary/amount）→ `check` 作用域门控 → 逐笔 `check_ledger` 四态判定；**失败件单列不改退出码**（missing_field/parse_error/unknown_year 等原因码） |
| 跨年对账接真结论 | ✅ | 逐笔按**稳定身份键** `enterprise_id\|year\|item_key` 登记 `ObservedItem`（content_sha256=本笔核查输入指纹）→ `--baseline` 四集合划分（新增/已修复/持续/稳定 + content_changed 标记）；`compare_nonpass` 唯一实现源不变 |
| scan 驱动报告导出 | ✅ | `scan --report`：结果直接组装 `ReportInput(check=…, reconcile=…)` → MD/XLSX/evidence 三件；单一渲染源 + 无外链 + 溯源断言沿用 M2 测试 |
| 指纹防篡改 | ✅ | evidence.json 记录报告自身 sha256；**测试锁定"报告改动一字 → 指纹必须对不上"**（`test_report_tampering_detected_by_evidence`） |
| 基准三套件 | ✅ | `tiered_boundary` 216/216 · `dual_version` 42/42 · `synthetic_ledger` 129/129（spending 扩节不触碰计提路径，基准无回退） |
| 测试 / 门禁 | ✅ | **179 项 py3.8+3.12 双绿**（新增 `test_scan_real.py` 7 项）；零字面量门禁 + 脱敏审计 OK；三生成器 `--check` 逐字节一致 |
| CI 实跑 | ⬜ | **本机无远端未跑 CI**——一律写"本地等价校验"，首推后据实补记（同 M0/M1/M2 纪律） |

**遗留显式 pending**（不阻断计算路径）：安全生产法 2014/2021 修正日期、GB 12268 现行版本号（M2 再试官方渠道仍不可取，续留 pending，clauses.json 登记）；2012 版进度门槛（无对应比例条款，显式 pending）。

---

## 二、M4 待办（基准：三类套件达标，指标进 README + 双版本差异报告）

> **M3 已提前吃掉的部分（勿重做）**：`bench` 三套件已全达标且退出码 0（216/216、42/42、129/129）；README 基准表现状列已更新为 M2 后数字；探活机制（注入缺陷→变红）已在 M0 建成。

按序执行（每步有验收门）：

1. **探活实测留痕**：对每套件做一次"注入缺陷 → 基准必须变红"的实跑留痕（M0 已有机制，M4 需**实测记录**进 plan/05 或 06——防"探活只是写了没跑过"）。
2. **基准指标表进 README 终稿**：README 评测基准一节升级为**最终指标口径**（各套件用例数/门槛/实测值/退出码语义），M5 打包后指标不变即可冻结。
3. **双版本差异报告可导出**：`diff` 现只有 stdout/JSON——M4 让 `diff --out` 导出 MD/XLSX 对照报告（复用 `report/` 单一渲染源；两版费率序列 `|` 连接的口径已锁进 diff 测试）。
4. **验收门**：`safefee bench` 三套件全达标且探活实测变红；`diff --out` 产物经无外链/字节冻结断言；README 指标表与 `bench` 实测一致；全链本地等价校验绿。

---

## 三、既定口径清单（**动了会打挂基准**，改前先对照本表）

| 口径 | 当前定稿 | 改动影响 |
|---|---|---|
| 段边界归属 | `[lower, upper)`；恰好等于分段点归下一段 | 引擎 + 真值 + `tiered_boundary` 三处（E2） |
| 金额量化 | `ROUND_HALF_UP` 两位小数 | 全部金额断言（E1） |
| 年度锚定 | 按日（2022-11-21 为界）；只给年度取该年 1 月 1 日 | 年度→版本映射测试（E3） |
| 门控作用域 | `calc`/`check`/`progress` + 第三态 `input_required`；`calc` 收窄到本次行业 | 退出码断言（E4） |
| 基准门槛 | 随 `manifest.benchmark_thresholds` 下发，缺失即退出码 2 | 基准判定（E7） |
| "未评估"语义 | 用例数 0 → `assessable=False`，不声称达标也不判未达标 | 基准判定（E8） |
| 失败件语义 | 批量扫描失败件不改退出码 | CLI 批量测试（E10） |
| 对账配对主键 | 稳定身份键（enterprise_id+year+item_key） | 四集合划分测试（E11） |
| 四态语义 | `不适用` 仅限原文例外；无条件义务缺失=`不符合`；无适用项=`未评估` | 支出核查 + 真值 + criteria（E12） |
| 数据目录优先级 | explicit > env > frozen > 源码上溯 > CWD | `find_data_dir` 分支测试（E18） |
| 报告字节承诺 | 默认含真实生成时间；"逐字节可复现"按同输入两次导出断言 | 报告测试（E21） |
| 零字面量豁免 | 定义性换算 + 精度约定 + 路径+规则名白名单 | 门禁扫描面（E6）——**真值库数值必须从规则包 JSON 推导，禁止复制字面量** |
| 报告溯源 | 有计提结论却无参数来源块（或行缺文号/条款/URL/抓取日期）→ 拒导 | 导出前断言（D3） |
| 电力分段 | 第四十三条生产/供应两套标准为**两个变体阶梯**，基准按独立阶梯枚举（`bench._ladders`） | bench + 真值 power 两例 |
| 2012 版进度门槛 | 无对应比例条款（第十四条是结余缓提规则）→ progress 作用域对 2012 版**显式 pending 拦截** | test_gate 活体样本 |
| 真值 id 唯一性 | 真值档案 id 必须全局唯一；`gen_synthetic --check` 检测陈旧文件 | 真值库守门 |
| 依据选择阈值（M2） | 第五十三条 85% 阈值作为**数据**下发 `basis_rules`（不写死在引擎） | 净额口径判定 + 参数来源块 |
| 变体级机制覆写（M2） | 机制取"变体覆写优先"（地质勘探/工程成本按费用比例） | engine + bench `_index_nodes` + diff `_index` 三处 |
| diff 配对覆盖（M2） | 超额累退"数值"= 分段费率序列（`\|` 连接）；两版都登记的行业记"已比对" | diff 九类覆盖门 |
| 参数来源块真出处（M2） | 导出前断言要求 文号 + 条款 + URL + 抓取日期非空 | 报告导出 |
| **scan 接真四态（M3 新）** | 台账 CSV 7 列逐笔四态判定；**失败件与核查结论（含不符合）都不改 scan 退出码**——处置交给报告与对账（与 `check` 退出码 1 语义区分） | CLI 批量测试（E10 同族） |
| **对账键（M3 新）** | ObservedItem 键 = `enterprise_id\|year\|item_key`；content_sha256=本笔核查输入指纹（只做 content_changed 标记） | 四集合划分 + reconcile 测试（E11） |
| **spending 覆盖（M3 新）** | 2022 版 41 条 / 2012 版 30 条（要点引用非全文转载）；关键词取自各节支出条款要点词 | `check`/`scan` 四态判定的命中面 |

---

## 四、本机环境坑（实测过，沿用 M1/M2 + M3 新增）

- `py -0p` 有 3.8.8 与 3.12；默认用 `py -3.12 -X utf8` 跑（中文控制台）。
- **M3 实测：Git Bash 里 `python` 命令返回 exit 49 且无任何输出（`python --version` 也是）——本机一律用 `py -3.12`（或 `py -3.8`）**，不要用裸 `python`。
- venv 段落一律 `python -m pip`；`PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏——出怪错先清 `__pycache__`）。
- 临时文件用工作区相对路径（Git Bash `/tmp` 与 Windows Python 路径不通）；子进程显式 `encoding="utf-8"`；生成器一律 `write_bytes`。
- 显示层偶发污染（Read 回读）：改文件优先整文件重写或断言计数替换。
- **gov.cn 抓取**：`curl -sSL` 可直连 gongbao/zhengceku 静态页；政策库检索 API 可用；flk.npc.gov.cn（JS 应用）、npc.gov.cn（TLS 握手失败/返回首页）、mem.gov.cn（JS 渲染）三处不可 curl。
- 真值库扩例后若删改 case_id，旧文件会触发 `--check` 陈旧告警（**这是特性**）：`find data/truth/cases data/truth/negatives -name "*.json" -delete` 再跑即可。
- **heredoc 里的中文/多行 Python**：`py -3.12 -X utf8 - << 'EOF'` 在 Git Bash 可用（M3 实测）；裸 `python - << EOF` 不行（exit 49 同源）。

## 五、关键命令速查

```bash
# 生成冻结产物 + 守门
py -3.12 -X utf8 tools/gen_rulesets.py --check
py -3.12 -X utf8 tools/gen_samples.py  --check
py -3.12 -X utf8 tools/gen_synthetic.py --check   # 含陈旧文件检测

# 两个扫描器（含阳性对照）
py -3.12 -X utf8 tools/scan_policy_literals.py --selftest && py -3.12 -X utf8 tools/scan_policy_literals.py
py -3.12 -X utf8 tools/dessensitize_audit.py --selftest && py -3.12 -X utf8 tools/dessensitize_audit.py

# 测试（双解释器；M3 实测裸 python 不可用）
PYTHONPATH=src py -3.12 -X utf8 -m pytest -q
PYTHONPATH=src py -3.8  -X utf8 -m pytest -q

# CLI 冒烟
PYTHONPATH=src py -3.12 -X utf8 -m safefee version && PYTHONPATH=src py -3.12 -X utf8 -m safefee selfcheck && PYTHONPATH=src py -3.12 -X utf8 -m safefee bench
PYTHONPATH=src py -3.12 -X utf8 -m safefee calc data/samples/archive-coal.json
PYTHONPATH=src py -3.12 -X utf8 -m safefee check data/samples/ledger-demo.csv --archive data/samples/archive-coal.json
PYTHONPATH=src py -3.12 -X utf8 -m safefee progress data/samples/archive-coal.json --accrued 100000 --used 40000
PYTHONPATH=src py -3.12 -X utf8 -m safefee diff --from-year 2020 --to-year 2024

# scan 全链（M3）：批量台账 → 四态核查 → 对账 → 报告
PYTHONPATH=src py -3.12 -X utf8 -m safefee scan <台账目录> --out <输出目录>
PYTHONPATH=src py -3.12 -X utf8 -m safefee scan <台账目录> --out <输出目录> --baseline <上轮scan-result.json> --report

# M3 全链本地等价校验（= CI 各 step 本地复现）
py -3.12 -X utf8 tools/gen_rulesets.py --check && py -3.12 -X utf8 tools/gen_samples.py --check && py -3.12 -X utf8 tools/gen_synthetic.py --check
py -3.12 -X utf8 tools/scan_policy_literals.py --selftest && py -3.12 -X utf8 tools/scan_policy_literals.py
py -3.12 -X utf8 tools/dessensitize_audit.py --selftest && py -3.12 -X utf8 tools/dessensitize_audit.py
PYTHONPATH=src py -3.12 -X utf8 -m pytest -q
PYTHONPATH=src py -3.12 -X utf8 -m safefee bench
```

## 六、M3 DoD checklist（逐项打勾，未做到写偏差说明）

- [x] 支出范围条目扩至十二节（2022 版 41 条 / 2012 版 30 条），逐条挂原文核对，`gen_rulesets.py --check` 逐字节一致
- [x] `check_ledger` 覆盖十二行业；四态语义不虚高保留（无条目=未评估）
- [x] `scan` 接真四态核查（7 列台账 CSV；失败件单列不改退出码；原因码含 unknown_year 新语义）
- [x] 跨年对账接真结论（稳定身份键四集合划分 + content_changed 标记；baseline 为上轮 scan-result.json）
- [x] scan 结果直接驱动报告导出（`--report`；check/reconcile 章节进 MD/XLSX；evidence.json 记录报告 sha256）
- [x] **指纹防篡改测试**：报告改动一字 → evidence.json sha256 必须对不上
- [x] `bench` 三套件仍全达标（216/216、42/42、129/129）——spending 扩节不触碰计提路径
- [x] 测试全绿（py3.8 + py3.12，179 项）；零字面量门禁 + 脱敏审计 OK
- [x] 里程碑状态回写（plan/00 + 05 + 06 + README + data/README + HANDOFF-M4 落盘）

## 七、禁止事项（沿用 M1/M2 + M3 教训）

- **不得手改** `data/rules/**` 与 `data/truth/**`（生成器唯一写入者；真值 `--check` 连"目录里多出的旧文件"都算漂移）。
- **不得**把未核对数值落库或写进代码；`status=pending` 必须配 `value: null`。
- **不得**用搜索摘要当原文依据（数值一律 curl 落盘后本地核对；检索 API 只用于定位 URL）。
- **不得**写"CI 绿"（本机无远端）；只写"本地等价校验"，CI 结论待首推后据实补记。
- **不得**在公开文档提其余项目业务领域（品牌隔离）。
- **不得**在 `tools/gen_synthetic.py` 里复制政策数值字面量（真值点一律从规则包 JSON 推导——零字面量门禁会对生成器报红）。
- **不得**把非煤矿山/武器装备/电力等"一类多变体"行业塞进单一 segments（变体各持独立阶梯，基准按 `_ladders` 枚举）。
- **不得**把依据选择阈值（85%）写死在引擎——它是**数据**（`basis_rules`），改数据即改判定（M2）。
- **不得**让 `scan` 因核查结论（含不符合）改退出码——那是"判出违规"不是"运行失败"；失败件（解析/读取层）同样不改退出码（M3：两层语义都锁进测试）。
- **不得**把 spending 匹配关键词当"全文检索"——它们是**要点词**（逐条挂原文核对的关键词子集，宁缺勿滥：未命中=未评估，不臆造命中）。

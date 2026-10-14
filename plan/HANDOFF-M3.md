# HANDOFF-M3（M2 → M3 交接快照）

> **✅ 本快照的 M3 待办已全部完成（2026-10-14，见 §六逐项打勾）——下一棒请读 [HANDOFF-M4.md](HANDOFF-M4.md) 从 M4 开始，勿重做本快照 §二。**

> **用法**：新对话用 `/goal 读取 "plan/HANDOFF-M3.md" 继续完成任务`（绝对路径由用户侧拼）。
> **上游**：[00-README总览.md](00-README总览.md) · [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §三 · [06-决策记录.md](06-决策记录.md) §六
> **快照时间**：2026-10-14（M2 收尾，同日完成 M1→M2）
> **上一棒**：[HANDOFF-M2.md](HANDOFF-M2.md)（§六 M2 待办已全部完成）

---

## 一、当前进度（M2 已完成，本地等价校验通过）

| 项 | 状态 | 证据 |
|---|---|---|
| 2022 版十二节全量落值 | ✅ | 八节 deferred 逐条挂原文核对落值（非煤矿山第十条**机制纠正为 `by_output`**、石油天然气第十四条、交通运输第二十四条、冶金第二十七条、机械制造第三十条、烟花爆竹第三十三条、民用爆炸物品第三十六条、武器装备第三十九条**五小类变体**）；`gen_rulesets.py --check` 逐字节一致 |
| 2012 版九类全量落值 | ✅ | 余下六类落值（非煤矿山第六条含石油 17/天然气 5、交通运输第九条、冶金第十条、机械制造第十一条、烟花爆竹第十二条**四段结构差异**、武器装备第十三条） |
| 引擎扩展 | ✅ | `by_revenue_rate`（交通运输单一比例）+ **变体级机制覆写**（地质勘探/工程成本按 `by_project_cost`）；三处机制解析同步（engine/bench/diff） |
| 依据选择判定接入 | ✅ | `accrual/basis.py` 的 `decide_basis` 接入 `compute_calc`：第七条从高提取、第五十二条跨行业、第五十三条净额口径（阈值 85% 作为**数据**下发 `basis_rules`）；档案属性缺失 → `inputs_required` 退出码 2；判定进 `AccrualResult.basis` 与报告 |
| 报告溯源接线 | ✅ | `build_report_input` 从规则包真 provenance 组装参数来源块（发布机关/文号/条款/URL/快照/sha256/抓取日期）；导出前 `_assert_traceability` 要求真出处（文号+条款+URL+抓取日期非空） |
| 年度锚定边界 | ✅ | `test_manifest.test_year_anchor_boundary_2022_vs_2023`：year=2022→2012 版 / year=2023→136 号（按日 2022-11-21 为界） |
| 真值库扩例 | ✅ | `data/truth/` **122 算例 + 7 误报对照**（每节至少 1 例 + 各行业全部分段点 × ±0.01 邻域）；`gen_synthetic.py --check` 逐字节一致 + 陈旧文件检测 |
| 基准三套件 | ✅ | `tiered_boundary` 216/216（72 个有限边界）· `dual_version` 42/42 · `synthetic_ledger` 129/129 |
| 验收门 | ✅ | `calc` 十二节全退出码 0；`diff` 九类配对全覆盖（`compared_industries` 9 类） |
| 测试 / 门禁 | ✅ | **172 项 py3.8+3.12 双绿**；零字面量门禁（token 扩至新增特征数值）+ 脱敏审计 OK；三生成器 `--check` 逐字节一致 |
| CI 实跑 | ⬜ | **本机无远端未跑 CI**——一律写"本地等价校验"，首推后据实补记（同 M0/M1 纪律） |

**M2 遗留显式 pending**（不阻断计算路径）：安全生产法 2014/2021 修正日期、GB 12268 现行版本号——**M2 再试官方渠道仍不可取**（flk.npc.gov.cn 仍为 JS 应用返回 SPA 骨架、`npc.gov.cn` 直连返回站点首页而非法条、gov.cn 检索接口未收录法律文本）→ 官方原文未取到不得写入，**续留 pending**（clauses.json 登记）。

---

## 二、M3 待办（支出核查与对账：四态判定 + 批量扫描 + 跨年对账 + 报告/证据链）

> **M2 已提前吃掉的部分（勿重做）**：`compute_calc` 已产出 `basis` 判定并进报告；`build_report_input` 参数来源块已接真 provenance；报告 MD/XLSX **单一渲染源** + 字节冻结已就位（`test_report.py`）；`export_report` 溯源断言已用真数据验证。

按序执行（每步有验收门）：

1. **支出范围核查四态判定接入编排层**：`spending/checker.py` 已有 `check_ledger`（四态 + 红线）与 `LedgerItem`，但首期只覆盖四行业（煤炭/建设工程/危险品/电力）的 spending 条目——**M3 按需扩 spending 条目到十二节**（各节"应当用于以下支出"条目 + 禁止性条款），并接 `check` 作用域门控（`check_ledger_file` 已就位）。
2. **批量台账扫描接真核查**：`cli/cmd_scan.py` 的 `_handler` 现为 `STATE_NOT_ASSESSED` 占位——M3 接真：逐 CSV 读台账 → 跑 `check_ledger` → 取四态结论；**失败件隔离不改退出码**（已锁测试）。
3. **跨年对账接真结论**：`batch/reconcile.py` 的 `compare_nonpass`（四集合划分：新增异常/已修复/持续异常/稳定通过）已就位，主键 = 稳定身份键（enterprise_id+year+item_key）；M3 把 scan 的 `state` 从占位换成真四态。
4. **报告/证据链导出接真**：`scan --out` 产出的 `scan-result.json` 现含占位结论——M3 让 scan 结果直接驱动报告（`build_report_input(check=...)`）；报告指纹防篡改（报告自身 sha256 已在 `evidence.json`，需断言"报告被改动即可检出"）。
5. **验收门**：支出核查覆盖度达标（真值对账 100% + 误报 0）；失败件隔离（不中断、不改退出码）；四集合划分正确（稳定身份键配对）；报告 MD/XLSX 结构一致 + 无外链 + 溯源完整；指纹可检出改动。

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
| 电力分段 | 第四十三条生产/供应两套标准为**两个变体阶梯**，基准按独立阶梯枚举边界（`bench._ladders`） | bench + 真值 power 两例 |
| 2012 版进度门槛 | 无对应比例条款（第十四条是结余缓提规则）→ progress 作用域对 2012 版**显式 pending 拦截** | test_gate 活体样本 |
| 真值 id 唯一性 | 真值档案 id 必须全局唯一（如边界档案按 `(bound, tag)` 编 id）；`gen_synthetic --check` 检测陈旧文件 | 真值库守门 |
| **依据选择阈值（M2 新）** | 第五十三条 85% 阈值作为**数据**下发 `basis_rules`（不写死在引擎） | 净额口径判定 + 参数来源块 |
| **变体级机制覆写（M2 新）** | 机制取"变体覆写优先"（地质勘探/工程成本按费用比例） | engine + bench `_index_nodes` + diff `_index` 三处 |
| **diff 配对覆盖（M2 新）** | 超额累退"数值"= 分段费率序列（`\|` 连接）；两版都登记的行业记"已比对" | diff 九类覆盖门 |
| **参数来源块真出处（M2 新）** | 导出前断言要求 文号 + 条款 + URL + 抓取日期非空 | 报告导出 |

---

## 四、本机环境坑（实测过，沿用 M1/M2）

- `py -0p` 有 3.8.8 与 3.12；默认用 `py -3.12 -X utf8` 跑（中文控制台）。
- venv 段落一律 `python -m pip`；`PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏——**M2 实测再遇 `Windows fatal exception: access violation`，先清 `__pycache__` 即恢复**）。
- 临时文件用工作区相对路径（Git Bash `/tmp` 与 Windows Python 路径不通，`pathlib` 读 `/tmp` 会 `FileNotFoundError`）；子进程显式 `encoding="utf-8"`；生成器一律 `write_bytes`。
- 显示层偶发污染（Read 回读）：改文件优先整文件重写或断言计数替换。
- **gov.cn 抓取**：`curl -sSL` 可直连 gongbao/zhengceku 静态页；政策库检索 API `https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary&q=<urlencode标题>` 可用（定位 URL 利器）；**flk.npc.gov.cn 是 JS 应用**（返回 SPA 骨架）、`npc.gov.cn` 直连返回**站点首页**（非文章正文）、mem.gov.cn 目录页 JS 渲染——这三处不可 curl。
- 真值库扩例后若删改 case_id，旧文件会触发 `--check` 陈旧告警（**这是特性**）：`find data/truth/cases data/truth/negatives -name "*.json" -delete` 再跑即可。

## 五、关键命令速查

```bash
# 生成冻结产物 + 守门
python tools/gen_rulesets.py && python tools/gen_rulesets.py --check
python tools/gen_samples.py  && python tools/gen_samples.py --check
python tools/gen_synthetic.py && python tools/gen_synthetic.py --check   # 含陈旧文件检测

# 两个扫描器（含阳性对照）
python tools/scan_policy_literals.py --selftest && python tools/scan_policy_literals.py
python tools/dessensitize_audit.py --selftest && python tools/dessensitize_audit.py

# 测试（双解释器）
py -3.12 -X utf8 -m pytest -q
py -3.8  -X utf8 -m pytest -q

# CLI 冒烟
python -m safefee version && python -m safefee selfcheck && python -m safefee bench
python -m safefee calc data/samples/archive-coal.json        # 十二节任一 → 退出码 0 输出金额
python -m safefee diff --from-year 2020 --to-year 2024       # 九类配对全覆盖
python -m safefee check data/samples/ledger-demo.csv --archive data/samples/archive-coal.json
python -m safefee progress data/samples/archive-coal.json --accrued 100000 --used 40000

# M2 全链本地等价校验（= CI 各 step 本地复现）
python tools/gen_rulesets.py --check && python tools/gen_samples.py --check && python tools/gen_synthetic.py --check
python tools/scan_policy_literals.py --selftest && python tools/scan_policy_literals.py
python tools/dessensitize_audit.py --selftest && python tools/dessensitize_audit.py
python -m pytest -q
python -m safefee version && python -m safefee selfcheck && python -m safefee bench
```

## 六、M2 DoD checklist（逐项打勾，未做到写偏差说明）

- [x] 2022 版 deferred 八节逐条核对落值（非煤矿山**机制纠正为按产量**、武器装备五小类变体拆分），`gen_rulesets.py --check` 逐字节一致
- [x] 2012 版余下六类落值（烟花爆竹分段结构与 2022 版不同须注意），九类全 verified
- [x] 依据选择判定接入 `compute_calc`：从高提取、属性缺失必索（退出码 2）、跨行业与净额口径留痕进结果与报告
- [x] 报告参数来源块接真 provenance，导出前溯源断言用真实数据验证
- [x] 年度锚定边界测试：year=2022→2012 版 / year=2023→136 号
- [x] 真值库随八节扩例（每节至少 1 例 + 新分段点边界），`synthetic_ledger` 仍 100%（129/129）
- [x] `safefee calc` 十二节全 0；`bench` 三套件仍全达标；`diff` 覆盖九类配对
- [x] 安全生产法修正日期 / GB 12268 版本号：**再试官方渠道仍不可取 → 显式续留 pending 并说明**
- [x] 里程碑状态回写（plan/00 + 05 + 06 + README + data/README + HANDOFF-M3 落盘）
- [x] 测试全绿（py3.8 + py3.12，172 项）；零字面量门禁 + 脱敏审计 OK

## 七、禁止事项（沿用 M1 + M2 教训）

- **不得手改** `data/rules/**` 与 `data/truth/**`（生成器唯一写入者；真值 `--check` 连"目录里多出的旧文件"都算漂移）。
- **不得**把未核对数值落库或写进代码；`status=pending` 必须配 `value: null`。
- **不得**用搜索摘要当原文依据（数值一律 curl 落盘后本地核对；检索 API 只用于定位 URL）。
- **不得**写"CI 绿"（本机无远端）；只写"本地等价校验"，CI 结论待首推后据实补记。
- **不得**在公开文档提其余项目业务领域（品牌隔离）。
- **不得**在 `tools/gen_synthetic.py` 里复制政策数值字面量（真值点一律从规则包 JSON 推导——零字面量门禁会对生成器报红）。
- **不得**把非煤矿山/武器装备/电力等"一类多变体"行业塞进单一 segments（变体各持独立阶梯，基准按 `_ladders` 枚举）。
- **不得**把依据选择阈值（85%）写死在引擎——它是**数据**（`basis_rules`），改数据即改判定（M2 新增）。

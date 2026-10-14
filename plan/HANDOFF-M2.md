# HANDOFF-M2（M1 → M2 交接快照）

> **用法**：新对话用 `/goal 读取 "plan/HANDOFF-M2.md" 继续完成任务`（绝对路径由用户侧拼）。
> **上游**：[00-README总览.md](00-README总览.md) · [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §三 · [06-决策记录.md](06-决策记录.md) §六
> **快照时间**：2026-10-14（M1 收尾，同日完成 M0→M1）
> **上一棒**：[HANDOFF-M1.md](HANDOFF-M1.md)（§二 M1 待办已全部完成，§六 DoD 逐项打勾）

---

## 一、当前进度（M1 已完成，本地等价校验通过）

| 项 | 状态 | 证据 |
|---|---|---|
| 官方原文快照库 | ✅ | `data/knowledge/raw/` 11 份 curl 直连落盘逐份 sha256；`clauses.json` 登记 8 项依据（6 verified + 2 显式 pending） |
| 计提标准逐条核对落值 | ✅ | 2022 版四节 verified（煤炭第七条 50/30/15/5 元、建设工程第十七条 3.5/3/2.5/2/1.5%、危险品第二十一条 4.5/2.25/0.55/0.2%、电力第四十三条生产六段+供应四段）+ 第五十一条 60%；2012 版三类 verified（煤炭第五条 30/15/5、建设工程第七条 2.5/2.0/1.5、危险品第八条 4/2/0.5/0.2）；其余八节 deferred 显式 pending 带理由 |
| M0 节次勘误 | ✅ | 2012 版实为第五/七/八条（非七/十三/十六）；石油天然气 2012 版并入非煤矿山第六条 |
| 真值库（双重记账） | ✅ | `data/truth/` 29 算例 + 5 误报对照；期望值走生成器独立计算路径（不调引擎），基准用引擎重算对账 |
| 基准三套件 | ✅ | `tiered_boundary` 150/150（**按独立阶梯枚举**）· `dual_version` 8/8 · `synthetic_ledger` 34/34 |
| 计提可算 | ✅ | `safefee calc` 已核对行业退出码 0 输出金额+条款依据；deferred 行业退出码 2 |
| 测试 / 门禁 | ✅ | 155 项 py3.8+3.12 双绿；零字面量门禁 + 脱敏审计 OK；三生成器 `--check` 逐字节一致（真值 `--check` 含陈旧文件检测） |
| 回写 | ✅ | plan/00+05+06、HANDOFF-M1 §六、data/README（8 份规则包指纹）、根 README 同步 |
| CI 实跑 | ⬜ | **本机无远端未跑 CI**——一律写"本地等价校验"，首推后据实补记（同 M0 纪律） |

**M1 遗留显式 pending**（不阻断计算路径）：安全生产法 2014/2021 修正日期、GB 12268 现行版本号（flk.npc.gov.cn 为 JS 应用、npc.gov.cn TLS 握手失败，官方原文未取到不得写入）。

---

## 二、M2 待办（计提引擎：依据选择判定 + 八节落值 + 溯源接线）

> **M1 已提前吃掉的部分（勿重做）**：原 M2 DoD ①"算例回归 100%（synthetic_ledger）"与 ②"边界枚举 100%（tiered_boundary）"**已随 M1 数据落库达标**；④"单位错配报 warning 不静默"已在 `compute_calc`/`truth.evaluate_case` 实现并有真值用例。M2 剩余主轴是 **③依据选择判定 + deferred 八节落值 + 报告溯源接线**。

按序执行（每步有验收门）：

1. **deferred 八节落值**（2022 版）：原文已在 `data/knowledge/raw/136-body.paragraphs.txt`（354 段在手，无需再抓）——非煤矿山第十条（金属露天 5/地下 15、核工业 25、非金属露天 3/地下 8、小型露天采石场 2 元——**机制实为按产量，M0 误标 by_revenue_tiered，须纠正**）、石油天然气第十四条（原油 20 元/吨、原气 7.5 元/千方 + 工程成本 2%）、交通运输第二十四条（普通货运 1%、客运/管道/危险品货运 1.5%）、冶金第二十七条（3%/1.5%/0.5%/0.2%/0.1%/0.05% 六段）、机械制造第三十条（2.35%/1.25%/0.25%/0.1%/0.05% 五段）、烟花爆竹第三十三条（4%/3%/2.5% 三段）、民用爆炸物品第三十六条（4%/2%/0.5%/0.2%）、武器装备第三十九条（五小类各一套，**须变体拆分**）。逐条抽值 → 落值 verified → `gen_rulesets.py --check`。
2. **2012 版余下六类落值**：非煤矿山第六条（石油 17 元/吨等）、交通运输第九条、冶金第十条、机械制造第十一条、烟花爆竹第十二条（**200 万/500 万分段点，与 2022 版结构不同**）、武器装备第十三条（五小类）。落值后 2012 版九类全 verified。
3. **依据选择判定接入编排层**：`accrual/basis.choose_mine_variant` 已实现**但 compute_calc 未接线**——多灾害并存从高提取（第七条）、档案属性缺失必索（`inputs_required` → 退出码 2）、跨行业经营（第五十二条：能分别核算按业务分别提、不能按占比最高业务）、承揽/承运净额口径（第五十三条：外购成本 >85% 营业收入可按净额）。判定结果（chosen/excluded/clause）进 AccrualResult 与报告。
4. **报告参数来源块接真数据**：`ReportInput.parameter_sources` 现为测试占位——把规则包 `provenance`（文号/条款/URL/快照/sha256/抓取日期）映射进参数来源块，导出前断言（`_assert_traceability`）用真实数据验证。
5. **年度锚定边界测试补齐**：档案只给年度取 1 月 1 日锚定——**year=2022 → 2012 版（2022-01-01 < 2022-11-21）、year=2023 → 136 号**；跨 2022-11-21 当年经营的按日口径说明写进报告参数块。
6. **验收门**：`safefee calc` 十二节全部退出码 0（给足依据量）；`safefee bench` 三套件仍全达标（真值库随八节扩例）；`safefee diff` 差异表覆盖全部九类配对。

---

## 三、既定口径清单（**动了会打挂基准**，改前先对照本表）

| 口径 | 当前定稿 | 改动影响 |
|---|---|---|
| 段边界归属 | `[lower, upper)`；恰好等于分段点归下一段 | 引擎 + 真值 + `tiered_boundary` 三处（E2） |
| 金额量化 | `ROUND_HALF_UP` 两位小数 | 全部金额断言（E1） |
| 年度锚定 | 按日（2022-11-21 为界）；只给年度取该年 1 月 1 日 | 年度→版本映射测试（E3） |
| 门控作用域 | `calc`/`check`/`progress` + 第三态 `input_required`；`calc` 收窄到本次行业 | 退出码断言（E4）；**deferred 行业被引擎以 NotCovered 拒（退出码 2），不产生 calc blocker** |
| 基准门槛 | 随 `manifest.benchmark_thresholds` 下发，缺失即退出码 2 | 基准判定（E7） |
| "未评估"语义 | 用例数 0 → `assessable=False`，不声称达标也不判未达标 | 基准判定（E8） |
| 失败件语义 | 批量扫描失败件不改退出码 | CLI 批量测试（E10） |
| 对账配对主键 | 稳定身份键（enterprise_id+year+item_key） | 四集合划分测试（E11） |
| 四态语义 | `不适用` 仅限原文例外；无条件义务缺失=`不符合`；无适用项=`未评估` | 支出核查 + 真值 + criteria（E12） |
| 数据目录优先级 | explicit > env > frozen > 源码上溯 > CWD | `find_data_dir` 分支测试（E18） |
| 报告字节承诺 | 默认含真实生成时间；"逐字节可复现"按同输入两次导出断言 | 报告测试（E21） |
| 零字面量豁免 | 定义性换算 + 精度约定 + 路径+规则名白名单 | 门禁扫描面（E6）——**真值库数值必须从规则包 JSON 推导，禁止复制字面量** |
| 报告溯源 | 有计提结论却无参数来源块 → 拒导 | 导出前断言（D3） |
| **电力分段（M1 新）** | 第四十三条生产/供应两套标准为**两个变体阶梯**，基准按独立阶梯枚举边界（`bench._ladders`） | bench + 真值 power 两例 |
| **2012 版进度门槛（M1 新）** | 无对应比例条款（第十四条是结余缓提规则）→ progress 作用域对 2012 版**显式 pending 拦截** | test_gate 活体样本 |
| **真值 id 唯一性（M1 新）** | 真值档案 id 必须全局唯一（如边界档案按 `(bound, tag)` 编 id）；`gen_synthetic --check` 检测陈旧文件 | 真值库守门 |

---

## 四、本机环境坑（实测过，沿用 M1 + 新增）

- `py -0p` 有 3.8.8 与 3.12；默认用 `py -3.12 -X utf8` 跑（中文控制台）。
- venv 段落一律 `python -m pip`；`PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏，出怪错先清 `__pycache__`）。
- 临时文件用工作区相对路径（Git Bash `/tmp` 与 Windows Python 路径不通）；子进程显式 `encoding="utf-8"`；生成器一律 `write_bytes`。
- 显示层偶发污染（Read 回读）：改文件优先整文件重写或断言计数替换。
- **gov.cn 抓取（M1 实测）**：`curl -sSL` 可直连 gongbao/zhengceku 静态页；政策库检索 API `https://sousuo.www.gov.cn/search-gov/data?t=zhengcelibrary&q=<urlencode标题>` 可用（定位 URL 利器）；**flk.npc.gov.cn 是 JS 应用**（返回 SPA 骨架）、npc.gov.cn 直连 TLS 握手失败、mem.gov.cn 目录页 JS 渲染——这三处不可 curl。
- 真值库扩例后若删改 case_id，旧文件会触发 `--check` 陈旧告警（**这是特性**）：删掉残留文件再跑即可。

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
python -m safefee calc data/samples/archive-coal.json        # 已核对行业 → 退出码 0 输出金额
python -m safefee diff --from-year 2020 --to-year 2024
python -m safefee check data/samples/ledger-demo.csv --archive data/samples/archive-coal.json
python -m safefee progress data/samples/archive-coal.json --accrued 100000 --used 40000

# M1 全链本地等价校验（= CI 各 step 本地复现）
python tools/gen_rulesets.py --check && python tools/gen_samples.py --check && python tools/gen_synthetic.py --check
python tools/scan_policy_literals.py --selftest && python tools/scan_policy_literals.py
python tools/dessensitize_audit.py --selftest && python tools/dessensitize_audit.py
python -m pytest -q
python -m safefee version && python -m safefee selfcheck && python -m safefee bench
```

## 六、M2 DoD checklist（逐项打勾，未做到写偏差说明）

- [ ] 2022 版 deferred 八节逐条核对落值（非煤矿山**机制纠正为按产量**、武器装备五小类变体拆分），`gen_rulesets.py --check` 逐字节一致
- [ ] 2012 版余下六类落值（烟花爆竹分段结构与 2022 版不同须注意），九类全 verified
- [ ] 依据选择判定接入 `compute_calc`：从高提取、属性缺失必索（退出码 2）、跨行业与净额口径留痕进结果与报告
- [ ] 报告参数来源块接真 provenance，导出前溯源断言用真实数据验证
- [ ] 年度锚定边界测试：year=2022→2012 版 / year=2023→136 号
- [ ] 真值库随八节扩例（每节至少 1 例 + 新分段点边界），`synthetic_ledger` 仍 100%
- [ ] `safefee calc` 十二节全 0；`bench` 三套件仍全达标；`diff` 覆盖九类配对
- [ ] 安全生产法修正日期 / GB 12268 版本号：再试官方渠道（或显式续留 pending 并说明）
- [ ] 里程碑状态回写（plan/00 + 05 + 06 + HANDOFF-M3 落盘）
- [ ] 测试全绿（py3.8 + py3.12）；零字面量门禁 + 脱敏审计 OK

## 七、禁止事项（沿用 M1 + M1 教训）

- **不得手改** `data/rules/**` 与 `data/truth/**`（生成器唯一写入者；真值 `--check` 现在连"目录里多出的旧文件"都算漂移）。
- **不得**把未核对数值落库或写进代码；`status=pending` 必须配 `value: null`。
- **不得**用搜索摘要当原文依据（数值一律 curl 落盘后本地核对；检索 API 只用于定位 URL）。
- **不得**写"CI 绿"（本机无远端）；只写"本地等价校验"，CI 结论待首推后据实补记。
- **不得**在公开文档提其余项目业务领域（品牌隔离）。
- **不得**在 `tools/gen_synthetic.py` 里复制政策数值字面量（真值点一律从规则包 JSON 推导——零字面量门禁会对生成器报红）。
- **不得**把非煤矿山/武器装备等"一类多变体"行业塞进单一 segments（电力双阶梯的教训：变体各持独立阶梯，基准按 `_ladders` 枚举）。

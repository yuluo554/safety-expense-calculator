# HANDOFF-M1（M0 → M1 交接快照）

> **用法**：新对话用 `/goal 读取 "plan/HANDOFF-M1.md" 继续完成任务`（绝对路径由用户侧拼）。
> **上游**：[00-README总览.md](00-README总览.md) · [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §二 · [06-决策记录.md](06-决策记录.md)
> **快照时间**：2026-10-14（M0 收尾）
> **M1 收尾（同日）**：本快照 §二 M1 待办已全部执行完毕（§六 DoD 逐项打勾）。M1 新增既定口径：①电力第四十三条为**生产/供应两套标准（变体阶梯）**，基准按独立阶梯枚举边界；②2012 版进度门槛无对应比例条款 → progress 作用域对 2012 版**显式 pending 拦截**；③2012 版节次勘误（煤炭第五条/建设工程第七条/危险品第八条）。下一棒读 [HANDOFF-M2 思路](05-数据计划与里程碑.md) §三 M2 行。

---

## 一、当前进度（M0 已完成，本地等价校验通过）

| 项 | 状态 | 证据 |
|---|---|---|
| 计划文档 00–06 定稿 | ✅ | `plan/` 七份文件（00–06 + 本快照） |
| 可运行骨架 | ✅ | `python -m safefee version` → `safefee 0.1.0` |
| 规则包生成器（冻结产物，初态全 `pending`） | ✅ | `python tools/gen_rulesets.py` 产 8 份；`--check` → `FROZEN_RULESETS_OK` |
| 分作用域 status 门控 | ✅ | `safefee selfcheck`：`calc` 12 条 / `check` 9 条 / `progress` 1 条未核对 |
| 三类计提机制 + 超额累退分段 + 支出四态 + 对账四集合 + 报告导出 | ✅ | 骨架 + 单测覆盖 |
| CLI 退出码 0/1/2/3 | ✅ | `tests/test_cli.py` 逐条断言 |
| 基准骨架（三类套件、门槛随 manifest、探活） | ✅ | `safefee bench`：`tiered_boundary` 159/159；另两套件**未评估**（M1 后生效） |
| 测试 | ✅ | **145 项**，py3.8 与 py3.12 **双绿**（~1.5 秒） |
| 零政策字面量门禁 + 脱敏审计器 | ✅ | `--selftest` 阳性对照通过；仓库扫描 OK |
| CI workflow（四矩阵 + PYTHONUTF8 + fetch-depth 0） | ✅（**本地等价**） | `.github/workflows/ci.yml` + `tests/test_ci_workflow.py`（PyYAML 解析 + 结构断言）。**未推送 → 未跑 CI** |

**M0 DoD 逐项结论**：见 [05-数据计划与里程碑.md](05-数据计划与里程碑.md) §二（D0-1…D0-17 全 ✅）。
**偏差说明**：无。M0 全部 DoD 项已真实执行并留证；唯一"未发生"的是 CI 实跑（无远端），**如实标注"待首推验证"**。

---

## 二、下一里程碑待办（M1：数据先行）—— ✅ 已完成（2026-10-14，逐项证据见 §六）

按序执行（每步都有验收门）：

1. **抓取原文**：`curl` 直连 gov.cn 落盘 `data/knowledge/raw/`（136 号正文 .docx 附件 + 2012 版公报页），逐份登记 sha256；**搜索摘要一律不采信**，数值以官方原文为准。
2. **逐条核对计提标准**：按办法条文（煤炭第七条、建设工程第十七条、危险品第二十一条、电力第四十三条、其余各节）逐条抽取 → 写入 `tools/gen_rulesets.py` 的源数据 → 置 `status="verified"` + `provenance`（文号/条款/URL/抓取日期/`verified=true`）。
3. **重生成并守门**：`python tools/gen_rulesets.py` → `--check` 逐字节一致 → `data/README.md` 登记 sha256。
4. **建合成真值库**：`tools/gen_synthetic.py` 产出 `data/truth/cases/*.json`（三类机制算例 + 恰好等于分段点边界档案 + 元/万元错配档案 + 误报对照集 + 双版本对照真值）；`--check` 逐字节一致。
5. **核对项收尾**：安全生产法修正/施行日期、应急管理部令第 8 号等文号的原文发布日期 —— 逐条核对后落库或显式保留 `pending`。
6. **验收门**：`safefee calc data/samples/archive-coal.json` 从**退出码 1（门控拦截）转为退出码 0 并输出金额**；`safefee bench` 的 `synthetic_ledger` 从"未评估"转为达标。

---

## 三、既定口径清单（**动了会打挂基准**，改前先对照本表）

| 口径 | 当前定稿 | 改动影响 |
|---|---|---|
| 段边界归属 | `[lower, upper)`；**恰好等于分段点归下一段** | 引擎 + 真值库 + 基准三处同步（D E2） |
| 金额量化 | `ROUND_HALF_UP` 两位小数 | 全部金额断言（E1） |
| 年度锚定 | **按日**（2022-11-21 为界）；只给年度时取该年 1 月 1 日 | 年度→版本映射测试（E3） |
| 门控作用域 | `calc`/`check`/`progress` 三作用域 + 第三态 `input_required`；**`calc` 收窄到本次行业** | 全部退出码断言（E4） |
| 基准门槛 | 随 `manifest.benchmark_thresholds` 下发，**缺失即退出码 2，不回落默认值** | 基准判定逻辑（E7） |
| "未评估"语义 | 用例数为 0 的套件 → `assessable=False`，**不声称达标也不判未达标**，不阻断退出码 | 基准判定（E8 同族） |
| 失败件语义 | 批量扫描失败件**不改退出码**（≠违规） | CLI 批量通路测试（E10） |
| 对账配对主键 | **稳定身份键**（`enterprise_id + year + item_key`），非内容指纹 | 四集合划分测试（E11） |
| 四态语义 | `不适用` 仅限"原文写了例外情形"；无条件义务缺失 = `不符合`；无适用项 → `未评估` | 支出核查引擎 + 真值 + criteria 三处（E12） |
| 数据目录优先级 | explicit > env > frozen(`_MEIPASS`/`_internal`) > 源码上溯 > CWD | `find_data_dir` 分支测试（E18） |
| 报告字节承诺 | 默认含真实生成时间；**"逐字节可复现"按"同输入两次导出"断言** | 报告测试（E21） |
| 零字面量豁免 | 定义性换算（10000/1e8）+ 精度约定（0.01）+ **路径+规则名**白名单（规则包生成器、扫描器自身） | 门禁扫描面（E6） |
| 报告溯源 | 有计提结论却无参数来源块 → **拒导**（半溯源不可接受） | 导出前断言（D3） |

---

## 四、本机环境坑（**只写实测过的**）

- `py -0p` 有 **3.8.8 与 3.12**；本机默认用 `py -3.12 -X utf8` 跑（中文控制台）。
- **venv 段落一律用 `python -m pip`**（Windows `py` 启动器会绕过 venv 装到系统 Python）。
- **`PYTHONDONTWRITEBYTECODE=1`**（pyc 偶发损坏：随机 FAIL / 测试数波动 / `unknown opcode`）；出怪错先清 `__pycache__`。
- **Git Bash `/tmp` 与 Windows Python 路径不通**；临时文件用工作区相对路径。
- **子进程输出落盘会注入 CRLF**（`subprocess.run(stdout=PIPE)` 文本模式）→ 本项目所有子进程调用都显式 `encoding="utf-8"`，生成器一律 `write_bytes`。
- **pytest 多时分批跑**（本项目 145 项 <2 秒，暂不需要）。
- 显示层偶发污染（Read 回读）：改文件优先整文件重写或断言计数替换。

---

## 五、关键命令速查

```bash
# 安装（venv 内）
python -m pip install -U pip && python -m pip install -e ".[dev]"

# 生成冻结产物 + 守门
python tools/gen_rulesets.py && python tools/gen_rulesets.py --check
python tools/gen_samples.py  && python tools/gen_samples.py --check
python tools/gen_synthetic.py && python tools/gen_synthetic.py --check

# 两个扫描器（含阳性对照）
python tools/scan_policy_literals.py --selftest && python tools/scan_policy_literals.py
python tools/dessensitize_audit.py --selftest && python tools/dessensitize_audit.py

# 测试（双解释器）
py -3.12 -X utf8 -m pytest -q
py -3.8  -X utf8 -m pytest -q

# CLI 冒烟
python -m safefee selfcheck
python -m safefee rulesets
python -m safefee bench
python -m safefee calc data/samples/archive-coal.json   # M1 前应为退出码 1（门控拦截）
python -m safefee diff --from-year 2020 --to-year 2024
```

**M0 本地等价校验全链**（= CI 各 step 的本地复现）：

```bash
python tools/gen_rulesets.py --check && python tools/gen_samples.py --check && python tools/gen_synthetic.py --check
python tools/scan_policy_literals.py --selftest && python tools/scan_policy_literals.py
python tools/dessensitize_audit.py --selftest && python tools/dessensitize_audit.py
python -m pytest -q
python -m safefee version && python -m safefee selfcheck && python -m safefee bench
```

---

## 六、M1 DoD checklist（逐项打勾，未做到写偏差说明）

- [x] 136 号正文 .docx 附件直连落盘 + 逐份 sha256 登记（`data/knowledge/raw/`，11 份：docx/htm/txt）
- [x] 十二节计提标准逐条核对落值：2022 版四节 verified（煤炭 50/30/15/5、建设工程 3.5/3/2.5/2/1.5%、危险品 4.5/2.25/0.55/0.2%、电力生产六段+供应四段）；其余八节 **deferred 显式留 pending 带理由**（条款已定位、数值 M2）
- [x] 双版本规则包（136 号 + 2012 版）数值落库（2012 版煤炭第五条 30/15/5、建设工程第七条 2.5/2.0/1.5、危险品第八条 4/2/0.5/0.2）；**M0 节次假设勘误按公报原文纠正**（第五/七/八条，非七/十三/十六）；`safefee diff` 差异项可对照（added 10 / rate_changed 1 / removed 3）
- [x] `tools/gen_rulesets.py --check` → FROZEN_RULESETS_OK（8 份逐字节一致）；`data/README.md` §一登记 8 份指纹
- [x] 合成台账含三类机制算例（煤炭四变体/建设工程三类别/危险品全分段+电力两套标准）+ 恰好等于分段点 ±0.01 邻域 + 元/万元错配 + 误报对照集（3 零命中 + 2 应降级）+ 双版本对照 6 例
- [x] `tools/gen_synthetic.py --check` → FROZEN_TRUTH_OK（29 份逐字节一致）；**双重记账**：期望值由生成器独立计算路径产出（不调引擎），基准用引擎重算对账
- [x] `safefee calc data/samples/archive-coal.json` 退出码 **1 → 0**，输出 3,600,000.00 元 + 第七条（危险品 1,350,000.00 第二十一条、建设工程 1,200,000.00 第十七条同验）
- [x] `safefee bench`：`dual_version` **8/8**、`synthetic_ledger` **29/29** 从"未评估"转为达标（`tiered_boundary` 150/150）
- [x] 待核对项逐条处置：部令第 8 号（2022-01-06 公布/2022-04-01 施行）、煤安监技装〔2018〕9 号（成文 2018-04-27）、技装 8 号（2018-05-02/08-01 施行）、调查 14 号（2018-06-04/09-01 施行）已 curl 公报/政策库原文核对；**安全生产法 2014/2021 修正日期与 GB 12268 版本号显式留 `pending`**（flk.npc.gov.cn 为 JS 应用无静态页、npc.gov.cn TLS 握手失败——clauses.json + data/README §二留痕）
- [x] 里程碑状态回写（plan/00 状态表 + 05 里程碑 + 06 决策含 C1 定夺与新进口径）

---

## 七、禁止事项

- **不得手改** `data/rules/**` 与 `data/truth/**`（生成器是唯一写入者；改体例走生成器整目录重生成）。
- **不得**把未核对数值落库或写进代码（`status=pending` 必须配 `value: null`）。
- **不得**用搜索摘要当原文依据（数值一律 curl 落盘后本地核对）。
- **不得**写"CI 绿"（本机无远端）；只写"本地等价校验"，CI 结论待首推后据实补记。
- **不得**在公开文档提其余项目业务领域（品牌隔离）。

"""M3 批量扫描接真核查测试（四态结论 + 稳定身份键对账 + 报告驱动 + 指纹防篡改）。

**覆盖的验收门**（HANDOFF-M3 §二.5）：

* 支出核查接真（十二节行业可核查、四态语义不虚高）；
* 失败件隔离（不中断、不改退出码）；
* 四集合划分正确（稳定身份键 ``enterprise_id+year+item_key`` 配对）；
* scan 结果直接驱动报告（check + reconcile 章节进 MD/XLSX）；
* **报告指纹防篡改**：报告被改动即可从 ``evidence.json`` 检出。
"""

import json
from pathlib import Path

import pytest

from safefee.cli.main import main
from safefee.evidence import sha256_bytes
from safefee.errors import EXIT_OK

ENTERPRISE_COLS = "enterprise_id,year,industry_id,item_key,subject,summary,amount"
COAL_ID = "90000000SYN0000001A"
MET_ID = "90000000SYN0000008H"


def _write_ledger(directory: Path, name: str, rows: list) -> None:
    lines = [ENTERPRISE_COLS] + [",".join(row) for row in rows]
    (directory / name).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


@pytest.fixture()
def ledger_dir(tmp_path):
    directory = tmp_path / "ledger"
    directory.mkdir()
    return directory


def test_scan_real_four_states(ledger_dir, tmp_path, capsys):
    """四态接真：命中允许=符合、命中红线=不符合、无条目=未评估（**绝不虚报符合**）。"""
    _write_ledger(ledger_dir, "one.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "煤矿安全改造支出", "120000.00"),
        (COAL_ID, "2024", "coal", "IT-002", "管理费用", "挪用于办公经费", "30000.00"),
        (COAL_ID, "2024", "coal", "IT-003", "安全费用", "无关支出", "100.00"),
    ])
    out = tmp_path / "out"
    assert main(["scan", str(ledger_dir), "--out", str(out)]) == EXIT_OK

    payload = json.loads((out / "scan-result.json").read_text(encoding="utf-8"))
    states = {f["item_key"]: f["state"]
              for f in payload["processed"][0]["findings"]}
    assert states["IT-001"] == "符合"
    assert states["IT-002"] == "不符合"
    assert states["IT-003"] == "未评估"
    assert payload["processed"][0]["redlines"][0]["item_key"] == "IT-002"
    # 稳定身份键：enterprise_id+year+item_key
    assert payload["observed"][0]["key"] == "%s|2024|IT-001" % COAL_ID


def test_scan_new_industries_covered(ledger_dir, tmp_path, capsys):
    """M3 扩节：冶金/交通运输等新入行业逐笔核查真四态（不再 NotCovered）。"""
    _write_ledger(ledger_dir, "met.csv", [
        (MET_ID, "2024", "metallurgy", "MT-001", "安全费用", "安全防护设施改造支出", "50000.00"),
        (MET_ID, "2024", "metallurgy", "MT-002", "管理费用", "挤占安全费用", "10.00"),
    ])
    out = tmp_path / "out"
    assert main(["scan", str(ledger_dir), "--out", str(out)]) == EXIT_OK
    payload = json.loads((out / "scan-result.json").read_text(encoding="utf-8"))
    states = {f["item_key"]: f["state"] for f in payload["processed"][0]["findings"]}
    assert states["MT-001"] == "符合"
    assert states["MT-002"] == "不符合"
    assert payload["processed"][0]["findings"][0]["clause"] == "第二十八条"


def test_scan_reconcile_four_sets(ledger_dir, tmp_path):
    """跨年对账接真：新增异常 / 持续异常 / 稳定按**稳定身份键**配对。"""
    _write_ledger(ledger_dir, "round1.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "煤矿安全改造支出", "120000.00"),
        (COAL_ID, "2024", "coal", "IT-002", "管理费用", "挪用于办公经费", "30000.00"),
    ])
    out1 = tmp_path / "out1"
    assert main(["scan", str(ledger_dir), "--out", str(out1)]) == EXIT_OK

    # 第二轮：旧违规已整改（变符合）+ 新违规出现 + 旧符合变未评估
    _write_ledger(ledger_dir, "round2.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "无关支出", "120000.00"),
        (COAL_ID, "2024", "coal", "IT-002", "安全费用", "煤矿安全改造支出", "30000.00"),
        (COAL_ID, "2024", "coal", "IT-009", "管理费用", "挪用于办公经费", "5.00"),
    ])
    out2 = tmp_path / "out2"
    assert main(["scan", str(ledger_dir), "--out", str(out2),
                 "--baseline", str(out1 / "scan-result.json")]) == EXIT_OK

    payload = json.loads((out2 / "scan-result.json").read_text(encoding="utf-8"))
    counts = payload["reconcile"]["counts"]
    assert counts["新增异常"] == 2          # IT-009（新违规）+ IT-001（符合 → 未评估，非 pass 集）
    assert counts["已修复"] == 1            # IT-002（同键，状态转符合）
    assert counts["持续异常"] == 0
    assert counts["稳定"] == 0
    assert payload["reconcile"]["content_changed"]  # 内容指纹变化另立标记


def test_scan_failure_isolation_real(ledger_dir, tmp_path, capsys):
    """失败件（缺列/坏数值）单列带原因码；好件结论照常产出，退出码不变。"""
    _write_ledger(ledger_dir, "good.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "煤矿安全改造支出", "100.00"),
    ])
    (ledger_dir / "badcols.csv").write_bytes(b"item_key,subject,summary,amount\n1,2,3,4\n")
    _write_ledger(ledger_dir, "badnum.csv", [
        (COAL_ID, "not-a-year", "coal", "IT-002", "安全费用", "煤矿安全改造支出", "100.00"),
    ])
    out = tmp_path / "out"
    assert main(["scan", str(ledger_dir), "--out", str(out)]) == EXIT_OK
    payload = json.loads((out / "scan-result.json").read_text(encoding="utf-8"))
    assert len(payload["processed"]) == 1
    reasons = {f["reason_code"] for f in payload["failures"]}
    assert reasons == {"missing_field", "unknown_year"}


def test_scan_drives_report(ledger_dir, tmp_path):
    """scan 结果直接驱动报告：MD/XLSX/evidence 三件产出，核查与对账章节进报告。"""
    _write_ledger(ledger_dir, "one.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "煤矿安全改造支出", "120000.00"),
        (COAL_ID, "2024", "coal", "IT-002", "管理费用", "挪用于办公经费", "30000.00"),
    ])
    out = tmp_path / "out"
    assert main(["scan", str(ledger_dir), "--out", str(out), "--report"]) == EXIT_OK
    md = (out / "报告.md").read_text(encoding="utf-8")
    assert "支出合规核查清单" in md
    assert "红线项（禁止性条目命中）" in md
    assert (out / "报告.xlsx").is_file()
    evidence = json.loads((out / "evidence.json").read_text(encoding="utf-8"))
    assert "报告.md" in evidence["entries"]
    assert "报告.xlsx" in evidence["entries"]


def test_report_tampering_detected_by_evidence(ledger_dir, tmp_path):
    """**指纹防篡改**：报告导出后内容被改动 → evidence.json 的 sha256 必须对不上。"""
    _write_ledger(ledger_dir, "one.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "煤矿安全改造支出", "120000.00"),
    ])
    out = tmp_path / "out"
    assert main(["scan", str(ledger_dir), "--out", str(out), "--report"]) == EXIT_OK

    md_path = out / "报告.md"
    evidence = json.loads((out / "evidence.json").read_text(encoding="utf-8"))
    recorded = evidence["entries"]["报告.md"]

    # 未改动：指纹一致
    assert sha256_bytes(md_path.read_bytes()) == recorded
    # 篡改一个字符：指纹必须对不上（"报告被改动即可检出"）
    tampered = md_path.read_text(encoding="utf-8").replace("符合", "不符合", 1)
    md_path.write_text(tampered, encoding="utf-8")
    assert sha256_bytes(md_path.read_bytes()) != recorded


def test_scan_no_matching_industry_rows_all_states_sum(ledger_dir, tmp_path):
    """多件混合：结论计数逐件累计（汇总口径与逐件口径一致）。"""
    _write_ledger(ledger_dir, "a.csv", [
        (COAL_ID, "2024", "coal", "IT-001", "安全费用", "煤矿安全改造支出", "1.00"),
    ])
    _write_ledger(ledger_dir, "b.csv", [
        (MET_ID, "2024", "metallurgy", "MT-001", "管理费用", "挤占安全费用", "2.00"),
    ])
    out = tmp_path / "out"
    assert main(["scan", str(ledger_dir), "--out", str(out)]) == EXIT_OK
    payload = json.loads((out / "scan-result.json").read_text(encoding="utf-8"))
    assert len(payload["observed"]) == 2
    states = sorted(item["state"] for item in payload["observed"])
    assert states == ["不符合", "符合"]

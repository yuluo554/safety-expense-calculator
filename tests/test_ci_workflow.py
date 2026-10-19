"""CI workflow 守门测试。

实测教训：非法 YAML 的 workflow 会让 GitHub **不建任何 job**（run 0 秒失败、
`jobs=0`），而 GitHub 端状态仍显示 ``active``、文件字节也洁净——**看状态、看字节
都查不出，只有真解析或真跑才暴露**。故本测试用 PyYAML 解析并逐 job 断言结构。

同族守门：**历史扫描类守门的环境必须配 ``fetch-depth: 0``**（否则 CI 浅克隆
静默空验，"CI 也跑了历史扫描"是假的）。

注：**未推送 = 未跑 CI**——本测试只证明 workflow 文件**可被解析且结构完整**，
不声称 CI 已绿（发布里程碑据实补记）。
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML 是 dev extra 的测试期依赖")

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow_files():
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def test_workflow_directory_exists():
    assert WORKFLOWS.is_dir()
    assert _workflow_files(), "至少应有一个 workflow 文件"


def test_all_workflows_are_parseable():
    """非法 YAML → GitHub 不建 job（0 秒失败）。必须真解析才拦得住。"""
    for path in _workflow_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), "%s 不是合法 YAML 映射" % path.name


def test_every_job_has_runs_on_and_steps():
    for path in _workflow_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = payload.get("jobs") or {}
        assert jobs, "%s 没有任何 job" % path.name
        for job_name, job in jobs.items():
            assert "runs-on" in job, "%s 的 job %s 缺 runs-on" % (path.name, job_name)
            assert job.get("steps"), "%s 的 job %s 缺 steps" % (path.name, job_name)


def test_every_checkout_uses_full_history():
    """历史扫描类守门依赖 git 历史 → 每个 checkout 必须 ``fetch-depth: 0``。"""
    found = False
    for path in _workflow_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (payload.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = step.get("uses", "")
                if uses.startswith("actions/checkout"):
                    found = True
                    depth = (step.get("with") or {}).get("fetch-depth")
                    assert depth == 0, (
                        "%s 的 job %s 的 checkout 缺 fetch-depth: 0（历史扫描会静默空验）"
                        % (path.name, job_name)
                    )
    assert found, "未找到 actions/checkout 步骤"


def test_ci_sets_pythonutf8_env():
    """编码守卫第三道：CI 的 python 不带 ``-X utf8``，必须靠环境变量兜住。"""
    for path in _workflow_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        text = str(payload)
        assert "PYTHONUTF8" in text, "%s 未设置 PYTHONUTF8（CI 中文输出会崩）" % path.name


def test_ci_matrix_covers_both_os_on_supported_interpreter():
    """双矩阵：ubuntu/windows × 3.12。

    **口径变更声明（2026-10-19，DEC1）**：原断言是"四矩阵 ubuntu/windows × 3.8/3.12"
    并把 ``3.8`` 写死。解释器底线抬到 3.12 后 3.8 不再是受支持口径，故本断言改为
    "两 OS × 受支持的 3.12"，并**反向断言不含已 EOL 的 3.8**——不是放宽：口径本身变了，
    且新断言比旧断言更严（旧断言只要求 3.8 在列，新断言要求 3.8 不得在列）。
    """
    for path in _workflow_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (payload.get("jobs") or {}).values():
            matrix = (job.get("strategy") or {}).get("matrix") or {}
            if not matrix:
                continue
            oses = matrix.get("os") or []
            versions = [
                str(v)
                for v in (matrix.get("python-version") or matrix.get("python_version") or [])
            ]
            assert len(oses) >= 2, "%s 的矩阵应覆盖两个 OS" % path.name
            assert versions, "%s 的矩阵缺 python-version" % path.name
            assert "3.12" in versions, "%s 的矩阵应覆盖受支持的 3.12" % path.name
            assert "3.8" not in versions, (
                "%s 的矩阵不应再含已 EOL 的 3.8（DEC1：底线 3.12）" % path.name
            )


def test_ci_installs_dev_extra_covering_test_time_dependency():
    """CI 的 extras 必须覆盖测试期依赖（PyYAML），否则守门在 CI 上静默跳过。"""
    for path in _workflow_files():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        text = str(payload)
        assert "[dev]" in text, "%s 未安装 dev extra" % path.name

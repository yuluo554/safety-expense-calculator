# RELEASE-v0.2.0 — 发布面回填：规则包复核锚 + `requires-python` 抬到 3.12

> 上一版：`v0.1.0`（2026-10-14）。
> 触发来源：轨 I（发布物一致性）I-1 —— `v0.1.0` 之后 `src/` 有 **1 个文件 / +37 行**的改动
> （`selfcheck` 新增规则包复核锚提示），**从未随任何 tag 发布过**。

## 一、相对 v0.1.0 改了什么

| 类别 | 内容 | 用户能否感知 |
|---|---|---|
`src/safefee/cli/cmd_selfcheck.py` | 新增 `_review_anchor_lines()`（+37 行）：读 `rules/manifest.json` 的 `review_interval` / `next_review`，在 `selfcheck` 末尾打印；逾期时追加 `! 已逾期 N 天…` | **能**：`selfcheck` 多 1–2 行输出 |
`requires-python` | `>=3.8` → **`>=3.12`** | **能（破坏性）**：3.8–3.11 装不上 |
`build-system` | `setuptools>=61` → **`>=77`**（PEP 639） | 构建期 |

**没有改**：计提公式、分段表、双版本对照数值、规则包内容（`manifest.json` 的
`review_interval` / `next_review` 在 v0.1.0 时就已下发），退出码语义（0/1/2/3），
CLI 子命令与旗标，报告格式。

**为什么这个提示合规**：本仓 plan/06 的口径清单写明「新增判据不得把既有仓库判红」。
`_review_anchor_lines()` 在清单读不出来时**静默返回空列表**，逾期也**只打印不改退出码**
（`return EXIT_OK` 不变）。实测：`selfcheck` 仍 exit 0。

## 二、为什么版本号是 0.2.0

`requires-python` 由 3.8 抬到 3.12 是**不兼容变更** → 0.x 阶段走 minor。

## 三、验证

| 项 | 命令 | 结果 |
|---|---|---|
| 全量测试（`[dev]` 口径） | `.venv/Scripts/python.exe -m pytest -q` | **210 passed, 4 skipped**（= README 的 214 项；4 项 skip 是缺 PySide6 的 GUI 交互） |
| 带 PySide6 | （装 `[gui]` 后） | **214 passed** |
| HEAD 的 CI | `commits/91770e0/check-runs` | 发布前 `91770e0` 全 `success` |
| **冻结态八项断言** | `tools/verify_frozen.py --dist dist/m5/safefee-cli` | `VERIFY_FROZEN_OK`，八项全 OK |
| 冻结态 `selfcheck`（含新增行） | `dist/m5/safefee-cli/safefee.exe selfcheck` | exit 0，末行 `规则包复核锚：复核周期 annual；下次复核 2027-10-14` |
| GUI exe 启动 | `QT_QPA_PLATFORM=offscreen ./safefee-gui.exe`（中立目录） | 持续运行未崩（45s 后由 timeout 终止 → 124，说明窗口存活） |

冻结态 `selfcheck` 末尾实测输出（**本轮新增**的那两行）：

```
规则包复核锚：复核周期 annual；下次复核 2027-10-14
```

## 四、附件与三方对撞

- 附件：`safefee-0.2.0-windows-x64-exe.zip` — **57,445,775 B** / 472 条目
- sha256 `2f3904fa3e233b86aac2d23ca96b355025ab6fda3c3e621e47cdca4c5148d987`
- 一致面：本地构建 / 二次打包（逐字节）/ GitHub asset digest / Release 正文
- 附 `SHA256SUMS-v0.2.0.txt`

**打包配方（本轮**新增**并留档，v0.1.0 未登记过 zip 打包方式）**：
`ZIP_DEFLATED(level=9)` + 条目按 UTF-8 字节序排序 + 全条目 `date_time=(1980,1,1,0,0,0)`
+ `create_system=0` + `external_attr=0o644<<16`。同一 dist 两次打包逐字节一致（已实测两次同 sha）。

## 五、历史结论是否需重跑

**不需要。** 计提公式、分段表、规则包数值**逐字节未改**，`bench` 三套件仍达标
（`verify_frozen.py` 八项含 bench）。新增的只是**提示行**，不参与判定。

---
name: manchi-component-dev
description: >
  Develop custom pipeline components (组件) for the Manchi smart-orchestration
  (智能编排) system. Use this skill whenever the user wants to create, modify,
  or export a Manchi orchestration component / 编排动作 / 自定义组件 / 执行链节点,
  or asks to "写一个组件", "做一个编排动作", "生成自定义节点", or turn some
  Python automation into a reusable Manchi component — even if they don't say the
  word "组件". The skill outputs a **component folder** `<name>/` (containing
  `manifest.json` + `component.py`) that can be dropped into
  ~/Documents/Manchi/components/ or zipped for export.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Manchi 组件开发 Skill

Guide Claude to produce a **directly-runnable** Manchi orchestration component:
a self-contained Python file plus a manifest describing its params. No hardcoded
values, no external side effects outside `artifacts_dir`.

Full spec (schema, types, boundary, dependency rules) lives in
[references/spec.md](references/spec.md). Read it before writing code. Use
[templates/component.template.py](templates/component.template.py) and
[templates/component.manifest.json](templates/component.manifest.json) as starters.
Validate output with the bundled script (see step 6).

## Workflow

1. **Clarify the component.** Ask (or infer) the essentials:
   - What does it do, and what is its **type**? `transform` (input→output),
     `output` (write a file, pass data through), `standalone` (no input, runs
     on its own), or `source` (fetches initial data, e.g. web/file/mail fetch).
   - What **input shape** must it receive? Set `input_requirement`
     (`none` / `any` / `text` / `mail` / `excel` / `csv` / `docx` / `pdf` /
     `json` / `table` / `file`). Parsing of mail/excel/docx is a **built-in
     source capability** — the component just declares what shape it needs.
   - What **params** should be user-configurable (never hardcode these)?
   - What does it return / produce?
2. **Pick `type` + `input_requirement`** and draft the `params` block.
3. **Write `component.py`** implementing `run(params: dict, context: dict) -> Any`.
   - Read ALL config from `params`. Read upstream data from
     `context["input_data"]`. Write outputs to `context["artifacts_dir"]`.
   - **输入数据已是解析后的形状（最关键）**：`input_requirement` 决定
     `context["input_data"]` 的类型，引擎已在调用前完成解析——
     - `excel` / `csv` / `table` → **`list[dict]`（行字典列表）**，千万不要
       再 `pd.read_excel(input_data)` 或 `open(input_data)`，否则 `FileNotFoundError`。
     - `text` / `docx` / `pdf` → 文本字符串。
     - `mail` → 邮件对象/字典列表。
     - `file` → 文件路径字符串（只有这时才需要自己读文件）。
     - `none` / `any` → 未加工，按你的设计处理。
   - **依赖要惰性导入**：不要在模块顶层 `import pandas` / `import openpyxl`
     这类重型库——运行时若没装会 `exec_module` 直接崩。改为在 `run()` 内
     `from openpyxl import ...`。只有确实用到的包才写进 `requires`。
   - Call the LLM via `context["llm_call"](messages, **kwargs)` if needed
     (never hardcode an API key/endpoint).
   - Keep `run` pure-ish: no module-level side effects; include an
     `if __name__ == "__main__":` self-test block. **自测里的 `input_data`
     要用「已解析后的形状」**（如 excel 组件用 `list[dict]`，不要去读文件）。
4. **Write `<name>.manifest.json`** mirroring the template. `name` must be
   `snake_case` and match the `.py` filename. List every configurable thing in
   `params`; list pip deps (unpinned) in `requires`.
5. **Self-review** against the boundary checklist in references/spec.md
   (§边界). Fix any "forbidden" pattern (hardcoded secret, destructive file
   ops, registry/service changes).
6. **Validate.** Run the bundled checker (it confirms `run()` exists/imports,
   manifest is valid, types/params well-formed, folder name matches
   `manifest.name`, and lints for hardcoded secrets/paths):
   ```bash
   python3 ${CODEBUDDY_SKILL_DIR}/scripts/validate_component.py <component-folder>
   # 或校验整个 components 根目录下的所有组件：
   python3 ${CODEBUDDY_SKILL_DIR}/scripts/validate_component.py ~/Documents/Manchi/components
   ```
   Resolve every FAIL (and every WARNING — WARNING 也需人工确认) before delivering.
7. **Deliver.** Output a folder `<name>/` (folder name == `manifest.name`)
   containing `manifest.json` + `component.py`. Then either:
   - **Install locally**: copy the whole `<name>/` folder into
     `~/Documents/Manchi/components/` (Windows:
     `C:/Users/<user>/Documents/Manchi/components/<name>/`), and append any new
     `requires` to that folder's `requirements.txt`.
   - **Export**: zip the whole `<name>/` folder (optionally include a
     per-component `requirements.txt`) so another user can import it.

## 组件运行失败的成因与红线（必读）

下面这些是导致"组件造出来却跑不起来"的真实坑，**每造一个组件都要逐条对照**：

1. **Excel/CSV 输入已被引擎解析成 `list[dict]`，再读文件必崩。**
   `input_requirement` 为 `excel`/`csv`/`table` 时，引擎（`actions.py`
   `_adapt_input` → `_to_records`）已经把源文件读成行字典列表并放进
   `context["input_data"]`。组件若写成 `pd.read_excel(input_data)` 或
   `open(input_data)`，会因 `input_data` 是 `list`/`dict` 而抛
   `FileNotFoundError` 或 `TypeError`。**正确做法**：直接遍历 `list[dict]`。
   （`file` 类型才是拿到路径，那时才自己读。）

2. **不要为了"读输入"去依赖 pandas/openpyxl。**
   表格输入已是 `list[dict]`，纯 Python 就能处理，组件通常 `requires: []`。
   只有"写出 Excel"才需要 `openpyxl`，且只在 `requires` 里声明它。

3. **严禁模块顶层硬导入重型/未声明依赖。**
   `import pandas` 写在文件顶部 → 运行时 venv 没装该包，`PluginManager`
   加载（`importlib.exec_module`）立刻抛 `ModuleNotFoundError`，组件直接
   加载失败。改为在 `run()` 内惰性 `import`；并把用到的包写进 `requires`。

4. **manifest 必须严格合规，否则 `validate_component.py` 判 FAIL。**
   - `params` 是**对象**（按参数名索引 `{name: {type,label,...}}`），
     **不是数组**。写成数组是早期坏样本漏过校验的根因。
   - 每个 param 的 `type` 只能是
     `string|number|boolean|select|textarea|file`，不要写 `string_or_int`、
     `integer` 之类。
   - 必须有 `display_name` 和 `source: "custom"`。
   - 文件夹名必须 == `manifest.name`（snake_case）。

5. **交付前必跑校验，且零 ERROR、WARNING 也要清零。**
   ```bash
   python3 ${CODEBUDDY_SKILL_DIR}/scripts/validate_component.py <组件文件夹>
   ```
   校验会查：manifest 合法、`run(params, context)` 存在、类型/params 合规、
   文件夹名匹配、以及在 Python 源码里扫描硬编码密钥/路径/注册表操作等红线。
   任何 FAIL 都修复后再交付。

6. **用真实形状自测。** `if __name__ == "__main__":` 里的 `input_data`
   要用解析后的形状（如 excel 组件传 `list[dict]`），不要自测里再去读文件。

> 记忆口诀：**excel 进来是 list[dict]，别再读文件；重依赖放 run 里惰性 import；
> manifest 的 params 是对象不是数组。**

## Examples

- "做一个把文本转大写的组件" → `type: transform`, `input_requirement: text`,
  one param `suffix`, returns uppercased text.
- "做个抓取网页正文保存为 markdown 的组件" → `type: standalone`
  (or `source` if it supplies the initial data), params `url`, writes a `.md`
  to `artifacts_dir`, `requires: ["requests"]`.

## Hard rules (non-negotiable)
- Every variable config comes from `params`. No hardcoded paths, secrets, or
  thresholds in the `.py`.
- Only read/write under `context["artifacts_dir"]` or system temp.
- Manifest `params` must cover everything the user could reasonably configure.
- `requires` uses **unpinned** package names (first version, per spec §依赖).

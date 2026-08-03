# Manchi 智能编排自定义组件系统设计方案

**核心思路：定义一套组件开发规范，让 AI 可以自动生成标准化的流水线组件，支持动态加载、参数配置、导入导出和依赖管理。**

---

## 背景

SmartOrch（智能编排）页面目前有 10 个内置动作类型，硬编码在前端（SmartOrch.vue 的 `actionTypes` 数组 + v-if 参数表单）和后端（actions.py 的 `ACTION_REGISTRY`）中。用户希望能够：

1. 在 Chat 中让 AI 生成自定义的编排组件
2. 每个组件是一个独立文件夹（含 manifest.json + component.py），遵循标准接口
3. 组件支持导入/导出（zip 分享）
4. 组件有依赖管理（每个组件有自己的 requirements.txt）
5. 参数可通过编排向导 UI 动态配置
6. 一个 Skill/Tool 定义组件开发标准，确保 AI 生成的组件可直接使用

---

## 架构概览

```
~/Documents/Manchi/components/
├── registry.json                # 自动生成的元数据索引
├── requirements.txt             # 全局合并的依赖列表
├── install_deps.py              # 自动安装缺失依赖的脚本
└── <component_name>/            # 每个组件一个文件夹（文件夹名 == manifest.name）
    ├── manifest.json            # 组件元数据
    └── component.py             # 组件逻辑

后端内置组件目录（随后端代码分发）：
backend/app/components/builtin/
├── ai_extract.manifest.json
├── ai_extract.py
├── export_excel.manifest.json
├── export_excel.py
└── ...
```

**统一组件模型：** 系统组件和个人组件共用完全相同的 `manifest.json + component.py` 结构。系统组件存放在后端代码中的 `builtin/` 目录，个人组件存放在用户目录下的 `components/` 目录。两者在运行时被合并到同一个 `COMPONENT_REGISTRY` 中，通过 manifest 中的 `source` 字段区分来源。

**组件类型：**
- `transform` — 接收输入数据，处理转换后返回新数据（如 ai_extract、ai_summarize）
- `output` — 产出文件（Excel/JSON/MD），数据透传不变（如 export_excel）
- `standalone` — 无需输入，独立运行
- `source` — 从外部源获取初始数据（类似邮件扫描）

**组件分类（元数据区分，架构统一）：**
- **系统组件（System）** — 内置的、基础通用的原生能力（当前 10 个动作 + 未来新增的内置组件），manifest 中 `source: "system"`
- **个人组件（Custom）** — 用户自定义开发或从外部导入的组件，manifest 中 `source: "custom"`
- **关键原则：系统组件和自定义组件使用完全相同的 manifest.json + component.py 模型。** 内置的 10 个动作也会被重构为同样的组件格式，统一从同一个注册表加载。区别仅在于 manifest 中的 `source` 字段和存放位置（系统组件随后端代码分发，自定义组件放在 `~/Documents/Manchi/components/`）。

---

## 第一阶段：组件规范定义 + Skill 文档

### 1.1 组件文件结构

**系统组件**（随后端代码分发，不可删除）：
```
backend/app/components/builtin/
├── ai_extract/
│   ├── ai_extract.manifest.json
│   └── ai_extract.py
├── export_excel/
│   ├── export_excel.manifest.json
│   └── export_excel.py
└── ... (10 个内置动作全部重构为此格式，每个动作一个文件夹)
```

**个人组件**（用户目录下，可导入/导出/删除，**一个文件夹对应一个组件**）：
```
~/Documents/Manchi/components/
├── registry.json                    # 自动生成的元数据索引
├── requirements.txt                 # 全局合并的依赖列表
├── install_deps.py                  # 自动安装缺失依赖的脚本
├── my_component/                    # 组件文件夹（名 == manifest.name）
│   ├── manifest.json                # 组件元数据配置
│   └── component.py                 # 组件代码文件
└── another_component/               # 另一个组件
    ├── manifest.json
    └── component.py
```

两种组件的 `manifest.json` 结构完全一致，唯一区别是 `source` 字段取值不同（`"system"` vs `"custom"`）。

### 1.2 manifest.json — 组件配置（独立配置文件）

```json
{
    "name": "my_component",
    "display_name": "我的组件",
    "description": "这个组件做什么",
    "version": "1.0.0",
    "author": "",
    "source": "custom",
    "type": "transform",
    "input_type": "any",
    "output_type": "any",
    "params": {
        "param_name": {
            "type": "string",
            "label": "参数标签",
            "default": "默认值",
            "required": true,
            "description": "参数说明"
        },
        "color": {
            "type": "select",
            "label": "颜色选择",
            "default": "red",
            "required": true,
            "description": "选择一个颜色",
            "options": ["red", "blue", "green"]
        }
    },
    "requires": []
}
```

**系统组件 manifest 示例（以 export_excel 为例）：**

```json
{
    "name": "export_excel",
    "display_name": "导出Excel",
    "description": "将当前数据导出为 Excel 文件",
    "version": "1.0.0",
    "author": "Manchi",
    "source": "system",
    "type": "output",
    "input_type": "any",
    "output_type": "any",
    "params": {
        "columns": {
            "type": "string",
            "label": "列名（逗号分隔）",
            "default": "",
            "required": false,
            "description": "留空=自动"
        },
        "filename": {
            "type": "string",
            "label": "文件名",
            "default": "导出.xlsx",
            "required": false,
            "description": "输出文件名"
        }
    },
    "requires": ["openpyxl"]
}
```

**参数类型参考：**

| type | 前端控件 | 说明 |
|------|----------|------|
| `string` | `<input>` | 文本输入 |
| `number` | `<input type="number">` | 数字输入 |
| `boolean` | `<input type="checkbox">` | 开关 |
| `select` | `<select>` | 下拉选择，需提供 options 数组 |
| `textarea` | `<textarea>` | 多行文本 |
| `file` | `<input> + 浏览按钮` | 文件路径选择 |

### 1.3 component.py — 组件执行代码

```python
"""
我的组件 - 组件描述

Component type: transform
Input: any → Output: any
"""

def run(params: dict, context: dict):
    """执行组件逻辑。

    Args:
        params: 用户配置的参数值（键名对应 manifest.json 中的 params 定义）
        context: 流水线上下文
            - input_data: 上一步骤/输入源的数据
            - source_type: "mail" | "text" | "file"
            - source_content: 原始文本内容
            - artifacts_dir: 产物输出目录
            - db: 数据库会话（可选）

    Returns:
        处理后的数据（作为下一步的 input_data）
        如果是 output 类型组件，返回 context["input_data"] 透传
    """
    # 你的逻辑代码
    result = []
    return result


# 组件也可以作为独立脚本运行测试
if __name__ == "__main__":
    result = run({"param_name": "test"}, {"input_data": "hello"})
    print(result)
```

### 1.4 组件边界条件

**允许做的事情：**
- 处理/转换文本、字典、列表数据
- 仅在 `artifacts_dir` 或临时目录内读写文件
- 调用外部 API（HTTP、数据库等）— 需在描述中注明
- 使用 AI/LLM（通过设置中配置的端点）
- 使用 Python 标准库或声明的依赖
- 调用 Windows COM（Outlook、Excel）
- 在 Manchi DB 中创建任务记录

**禁止做的事情：**
- 修改核心系统文件（后端代码、其他组件文件）
- 持久化系统修改（注册表、服务、环境变量）
- 在 artifacts_dir 外进行破坏性文件操作
- 硬编码密钥/令牌 — 必须通过参数传入
- 网络安全扫描或渗透测试
- 执行来自不可信源的代码

### 1.5 创建 Skill 文档

**新文件：** `docs/manchi-component-skill.md`

完整的 Skill 文档，包含：
1. 组件接口规范完整说明
2. 每种组件类型的代码模板和示例
3. 参数定义规则与类型参考
4. 组件边界条件
5. 导出/导入格式规范（.zip 结构）
6. 测试指引
7. **依赖版本规则：第一版要求所有组件必须使用当前最新版本的依赖，不锁定版本号（如直接写 `pandas` 而非 `pandas>=1.5.0`），以最大限度降低版本冲突风险。后续版本再引入版本锁定机制。**

该文档双重用途：
- 可作为 Claude Code Skill 加载
- 可单独在其它 IDE 中使用

### 1.6 前端：动态参数表单组件

**新文件：** `frontend/manchi-ui/src/components/orch/ParamForm.vue`

通用参数表单组件，读取 manifest.json 中的 `params` 定义，自动渲染对应表单控件：
- `string` → `<input>`
- `number` → `<input type="number">`
- `boolean` → `<input type="checkbox">`
- `select` → `<select>` 下拉框
- `textarea` → `<textarea>`
- `file` → `<input> + 浏览按钮`

用于替换当前 SmartOrch.vue 中的 v-if/v-else-if 硬编码参数表单链。

---

## 第二阶段：测试 Skill

### 2.1 创建示例组件

使用 Skill 标准手动创建 2-3 个示例组件：

| 组件名 | 类型 | 功能 |
|--------|------|------|
| `csv_to_markdown` | transform | 将 CSV 文本转换为 Markdown 表格 |
| `web_fetcher` | standalone | 抓取 URL 并返回文本内容 |
| `json_filter` | transform | 按条件过滤字典列表 |

### 2.2 验证运行

测试流程：
1. 将组件放到 `~/Documents/Manchi/components/<name>.py`
2. 用 `importlib` 动态导入
3. 调用 `run(params, context)` 测试
4. 验证输出是否符合预期

---

## 第三阶段：后端插件架构

### 3.1 插件管理器服务

**新文件：** `backend/app/services/plugin_manager.py`

`PluginManager` 类（**一个文件夹对应一个组件**：`components/<name>/manifest.json` + `components/<name>/component.py`）：

| 方法 | 说明 |
|------|------|
| `discover_components()` | 扫描 `~/Documents/Manchi/components/` 下每个子文件夹，读取其中的 `manifest.json`，返回 `name -> manifest` |
| `get_component_meta(name)` | 返回某组件的解析后元数据 |
| `run_component(name, params, context)` | 动态导入 `<name>/component.py` 并调用 `run(params, context)` |
| `export_component(name)` | 把 `<name>/` 整个文件夹打包为 zip 字节流 |
| `import_component(zip_bytes)` | 解压 zip 到 `components/<name>/`，并把 `requires` 合并进全局 `requirements.txt` |
| `list_components(category)` | 列出组件（按 manifest 的 `source` 筛选 system/custom） |
| `install_dependencies()` | pip 安装全局 `requirements.txt` 中缺失的依赖 |

**懒加载 + 缓存策略：**
- 只在首次请求或文件变更时重新扫描目录
- 组件模块按 `(路径, mtime)` 缓存，mtime 不变则复用已导入的模块对象，避免重复 import
- 文件 mtime 变化自动失效对应缓存

**加载伪代码（folder-based）：**
```python
import importlib.util
import json
import os
import zipfile
import io
from pathlib import Path

COMPONENTS_DIR = Path(os.environ.get(
    "MANCHI_COMPONENTS",
    os.path.expanduser("~/Documents/Manchi/components"),
))
GLOBAL_REQS = COMPONENTS_DIR / "requirements.txt"

_module_cache: dict[str, tuple[float, object]] = {}  # name -> (mtime, module)


def discover_components() -> dict[str, dict]:
    """扫描 components/<name>/manifest.json，返回 name -> manifest。"""
    result: dict[str, dict] = {}
    if not COMPONENTS_DIR.is_dir():
        return result
    for folder in sorted(COMPONENTS_DIR.iterdir()):
        mj = folder / "manifest.json"
        if folder.is_dir() and mj.exists():
            meta = json.loads(mj.read_text(encoding="utf-8"))
            # 文件夹名须等于 manifest.name
            if meta.get("name") == folder.name:
                result[folder.name] = meta
    return result


def _load_module(name: str):
    """按 mtime 缓存动态导入 <name>/component.py。"""
    py_path = COMPONENTS_DIR / name / "component.py"
    mtime = py_path.stat().st_mtime
    cached = _module_cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]
    spec = importlib.util.spec_from_file_location(f"_manchi_{name}", str(py_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    _module_cache[name] = (mtime, mod)
    return mod


def run_component(name: str, params: dict, context: dict):
    mod = _load_module(name)
    if not hasattr(mod, "run"):
        raise ValueError(f"组件 {name} 缺少 run() 函数")
    return mod.run(params or {}, context)


def export_component(name: str) -> bytes:
    """把 <name>/ 整个文件夹打包成 zip。"""
    src = COMPONENTS_DIR / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(src))
    return buf.getvalue()


def import_component(zip_bytes: bytes) -> str:
    """解压 zip 到 components/<name>/，并合并依赖。"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # 从压缩包内 manifest 推断组件名
        names = zf.namelist()
        manifest_entry = next((n for n in names if n.endswith("manifest.json")), None)
        if manifest_entry is None:
            raise ValueError("zip 内缺少 manifest.json")
        # 兼容根目录直接放 manifest.json 或 <name>/manifest.json 两种布局
        top = manifest_entry.split("/")[0] if "/" in manifest_entry else "."
        meta = json.loads(zf.read(manifest_entry))
        name = meta["name"]
        dest = COMPONENTS_DIR / name
        dest.mkdir(parents=True, exist_ok=True)
        # 统一解压为 <name>/manifest.json + <name>/component.py
        for n in names:
            data = zf.read(n)
            rel = n[len(top) + 1:] if (top != "." and n.startswith(top + "/")) else n
            if not rel:
                continue
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_bytes(data)
    _merge_requires(meta.get("requires", []), name)
    return name


def _merge_requires(requires: list[str], name: str) -> None:
    """把组件依赖去重合并进全局 requirements.txt（带来源注释）。"""
    existing: list[str] = []
    if GLOBAL_REQS.exists():
        existing = GLOBAL_REQS.read_text(encoding="utf-8").splitlines()
    base = [l for l in existing if not l.strip().startswith("#") and l.strip()]
    for pkg in requires:
        if pkg and pkg not in base:
            existing.append(pkg)
            existing.append(f"# 来自组件: {name}")
    GLOBAL_REQS.write_text("\n".join(existing) + "\n", encoding="utf-8")


def install_dependencies() -> None:
    """只装全局 requirements.txt 中缺失的依赖（diff 模式）。"""
    if not GLOBAL_REQS.exists():
        return
    import importlib.util, subprocess, sys
    for line in GLOBAL_REQS.read_text(encoding="utf-8").splitlines():
        pkg = line.split("#")[0].strip()
        if not pkg:
            continue
        top = pkg.split("==")[0].split(">=")[0].split("<")[0].strip()
        if importlib.util.find_spec(top.replace("-", "_")) is None:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=False)
```

### 3.2 组件 API 端点

**新文件：** `backend/app/routers/components.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/components` | 列出所有组件（system + custom），返回元数据 |
| `GET` | `/api/components/{name}` | 获取单个组件元数据 |
| `POST` | `/api/components/import` | 导入 .zip 组件文件（multipart 上传） |
| `GET` | `/api/components/{name}/export` | 下载个人组件为 .zip |
| `DELETE` | `/api/components/{name}` | 删除个人组件 |
| `POST` | `/api/components/install-deps` | 安装所有未安装的依赖 |

**统一组件注册：** 系统组件也重构为 manifest.json 格式。原有 `actions.py` 中的 `ACTION_REGISTRY` 将改为从一组内置的 manifest 定义 + handler 函数生成。最终只有一个注册表，包含所有组件：

```
COMPONENT_REGISTRY = {
    "ai_extract":      { manifest: {...},  handler: _action_ai_extract },
    "export_excel":    { manifest: {...},  handler: _action_export_excel },
    "my_custom_comp":  { manifest: {...},  handler: <dynamic_import> },
    ...
}
```

前端通过每个组件的 manifest 中的 `source` 字段区分显示样式：
- `source: "system"` → 系统组件标签
- `source: "custom"` → 个人组件标签

### 3.3 集成到流水线执行器

**修改：** `backend/app/services/orchestrator/engine.py`

原有的 `ACTION_REGISTRY` 和 `PluginManager` 合并为统一的 `COMPONENT_REGISTRY`：

```python
# 统一注册表：系统组件 + 个人组件
COMPONENT_REGISTRY: dict[str, ComponentEntry] = {}

def register_system_components():
    """注册内置系统组件"""
    for name, (manifest, handler) in BUILTIN_COMPONENTS.items():
        COMPONENT_REGISTRY[name] = ComponentEntry(manifest=manifest, handler=handler, source="system")

def register_custom_components():
    """注册文件系统中的个人组件"""
    for name, manifest in plugin_manager.discover_components().items():
        COMPONENT_REGISTRY[name] = ComponentEntry(
            manifest=manifest,
            handler=lambda p, c: plugin_manager.run_component(name, p, c),
            source="custom"
        )

def run_action(action_config, ctx):
    action_type = action_config.get("type", "")
    params = action_config.get("params", {}) or {}

    entry = COMPONENT_REGISTRY.get(action_type)
    if entry is None:
        raise ValueError(f"未知的动作类型：{action_type}")
    return entry.handler(params, ctx)
```

### 3.4 注册路由

**修改：** `backend/app/main.py`
- `from app.routers import components`
- `app.include_router(components.router)`

### 3.5 依赖管理

**新脚本：** `backend/app/services/install_component_deps.py`

导入组件时：
1. 读取组件的 `requires` 字段
2. 追加到 `~/Documents/Manchi/components/requirements.txt`
3. 运行 `pip install -r requirements.txt` 安装缺失依赖

---

## 第四阶段：前端集成

### 4.1 加载自定义组件

**修改：** `frontend/manchi-ui/src/pages/SmartOrch.vue`

1. `onMounted` 时额外请求 `GET /api/components` 获取所有组件列表
2. actionTypes 按来源分组：
   - **系统组件**（内置 10 个 + 未来新增）
   - **个人组件**（用户自定义 + 导入的）
3. 自定义组件使用 `ParamForm.vue` 动态渲染参数表单
4. `serializeActionParams`/`normalizeActionParams` 改为通用逻辑

### 4.2 组件管理界面

在 SmartOrch 页面头部添加入口：
- "管理组件" 按钮
- 弹窗显示所有个人组件列表及其元数据
- 导入按钮（选择 .zip 文件）
- 导出按钮（每个组件）
- 删除按钮（每个组件）
- "安装依赖" 按钮

### 4.3 动态参数表单

将 SmartOrch.vue 中当前 v-if/v-else-if 链（第 178-239 行）替换为：

```vue
<!-- 系统组件：保留原有静态表单 -->
<template v-if="isSystemAction(a.type)">
  ...原有 v-if/v-else-if...
</template>
<!-- 自定义组件：动态渲染 -->
<template v-else>
  <ParamForm :params-def="componentParams[a.type]" v-model="a.params" />
</template>
```

---

## 第五阶段：Chat/Tool 集成

### 5.1 添加 LLM Tool

**修改：** `backend/app/services/llm/tools.py`

新增 `create_component` 工具：

| 属性 | 值 |
|------|-----|
| 名称 | `create_component` |
| 描述 | "按照组件开发规范创建自定义编排组件" |
| 参数 `name` | string, 必填 — 组件标识（snake_case） |
| 参数 `display_name` | string, 必填 — 显示名称 |
| 参数 `description` | string, 必填 — 功能描述 |
| 参数 `component_type` | enum, 必填 — transform/output/standalone/source |
| 参数 `code` | string, 必填 — component.py 的完整 Python 代码 |
| 参数 `params_def` | JSON, 可选 — manifest.json 的参数定义 |
| 参数 `dependencies` | string[], 可选 — 需要的 pip 包 |

Tool 处理器逻辑：
1. 验证代码包含 `run()` 函数
2. 创建文件夹 `~/Documents/Manchi/components/{name}/`
3. 在其中写入 `component.py` 与 `manifest.json`
4. 将依赖合并到全局 requirements.txt
5. 运行 `install_deps.py`
6. 返回组件元数据

### 5.2 系统 Agent Tool

当用户请求 AI 创建组件时，通过 Tool 调用：
1. 读取 Skill 规范文档
2. 生成符合规范的组件代码和 manifest
3. 调用 `POST /api/components/import` 注册组件
4. 返回组件给用户

---

## 实施顺序总结

| 步骤 | 操作 | 涉及文件 |
|------|------|----------|
| **P1.1** | 编写组件规范 + Skill 文档 | `docs/manchi-component-skill.md` |
| **P1.2** | 创建 ParamForm.vue | `frontend/.../ParamForm.vue` |
| **P2.1** | 创建 2-3 个示例组件 | `~/Documents/Manchi/components/*/` |
| **P3.1** | 创建 PluginManager | `backend/app/services/plugin_manager.py` |
| **P3.2** | 重构内置动作为统一组件格式 | `backend/app/components/builtin/`（新建目录） |
| **P3.3** | 创建 components 路由 | `backend/app/routers/components.py` |
| **P3.4** | 统一 COMPONENT_REGISTRY + 集成到引擎 | `backend/.../engine.py`（修改） |
| **P3.5** | 注册路由到 main.py | `backend/app/main.py`（修改） |
| **P4.1** | 前端加载自定义组件 | `frontend/.../SmartOrch.vue`（修改） |
| **P4.2** | 组件管理 UI | `frontend/.../SmartOrch.vue`（修改） |
| **P5.1** | 添加 create_component LLM 工具 | `backend/.../tools.py`（修改） |
| **P5.2** | Agent Tool 集成 | Tool 定义 |

---

## 验证方案

1. **Skill 测试**：用 Skill 文档指导 AI 生成一个组件，验证符合规范
2. **插件发现**：启动后端，验证 `GET /api/components` 返回系统 + 个人组件
3. **自定义动作**：创建一个包含自定义组件的规则，运行，验证输出
4. **导入/导出**：导出组件为 zip，删除，重新导入，验证可用
5. **依赖管理**：创建需要 pandas 的组件，验证自动安装依赖
6. **Chat 创建**：在 Chat 中说"创建一个把文本转大写的组件"，验证生成可用
7. **回归测试**：所有 10 个内置动作仍然正常工作

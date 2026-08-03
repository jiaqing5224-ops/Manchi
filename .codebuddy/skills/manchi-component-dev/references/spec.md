# Manchi 组件规范（Skill 参考）

本文件是 `manchi-component-dev` skill 的权威规范摘要。系统级完整设计见仓库
`plan/Manchi组件系统设计方案.md` 与 `plan/组件生成能力-分析规划.md`。

## 1. 组件契约（contract）

每个组件是**一个文件夹**，放在 `~/Documents/Manchi/components/`（Windows：
`C:/Users/<user>/Documents/Manchi/components/`）。文件夹名即组件 id，须与
`manifest.json` 的 `name` 一致：

```
<name>/                  # 组件文件夹（文件夹名 == manifest.name）
├── manifest.json        # 元数据 + 参数定义
├── component.py         # 逻辑（实现 run(params, context)）
└── requirements.txt     # 可选：本组件依赖，便于单独分享
```

### component.py 接口
```python
def run(params: dict, context: dict) -> Any:
    """
    params:  用户配置，键名对应 manifest.json 的 params 定义
    context: {
        input_data,        # 上一步/输入源数据（已按 input_requirement 解析）
        artifacts_dir,     # 产物输出目录（唯一允许写文件的稳定位置）
        source_type, source_content, source_file_path,
        db,                # 可选：SQLAlchemy session
        llm_call,          # 可选：经配置端点的 LLM 调用封装
    }
    return: 处理后数据，作为下一步的 input_data
    """
```

## 2. 组件类型 `type`

| type | 是否有上游输入 | 说明 |
|------|----------------|------|
| `transform` | 是 | 接收数据→转换→返回新数据（最常用） |
| `output` | 是 | 产出文件/副作用，`current_data` 透传 |
| `standalone` | 否 | 无需输入、独立运行 |
| `source` | 否 | 自己从外部获取初始数据（web抓取/读文件/邮件扫描） |

## 3. 输入形状约束 `input_requirement`

取值：`none` | `any` | `text` | `mail` | `excel` | `csv` | `docx` | `pdf` | `json` | `table` | `file`

- 解析（邮件/Excel/docx/pdf 等）是**输入源的内置能力**，组件不负责解析，
  只通过 `input_requirement` 声明"我需要什么形状的数据"。
- `input_requirement: none` → 只能作为链路起点（`standalone`/`source`）。
- `excel`/`csv`/`docx`/`pdf` 的 `input_data` 已是解析后的规整结构
  （表格→行 dict 列表；文档→文本）。

## 4. manifest.json 字段

```json
{
  "name": "snake_case_id",
  "display_name": "显示名",
  "description": "功能描述",
  "version": "1.0.0",
  "author": "",
  "source": "custom",
  "type": "transform",
  "input_requirement": "any",
  "output_type": "any",
  "requires": ["openpyxl"],
  "params": {
    "param_name": {
      "type": "string",
      "label": "参数标签",
      "default": "",
      "required": false,
      "description": "参数说明",
      "options": ["a", "b"]   // 仅 type=select 需要
    }
  }
}
```

### params 类型 → 前端控件
| type | 控件 |
|------|------|
| `string` | 文本输入 |
| `number` | 数字输入 |
| `boolean` | 开关 |
| `select` | 下拉（需 `options`） |
| `textarea` | 多行文本 |
| `file` | 路径选择 |

## 5. 边界（允许 / 禁止）

**允许**
- 处理/转换文本、字典、列表
- 仅在 `artifacts_dir` 或临时目录读写文件
- 调用外部 HTTP API / 数据库（描述中注明）
- 使用 Python 标准库或 `requires` 声明的依赖
- 本地自动化（openpyxl / python-docx / pdfplumber / playwright / Windows COM 等）
- 经 `context["llm_call"]` 调用 LLM（不硬编码 key）
- 在 Manchi DB 创建任务记录

**禁止（红线）**
- 修改核心系统文件 / 其他组件文件
- 持久化系统修改（注册表、服务、环境变量）
- 在 `artifacts_dir` 外的破坏性文件操作
- 硬编码密钥/令牌（一律走 `params`）
- 网络扫描、渗透、未授权访问
- 执行不可信来源的任意代码
- 需要管理员提权的高危操作

## 6. 依赖规则

- 所有 pip 依赖写入 manifest 的 `requires`（**不锁版本号**，第一版最大化兼容）。
- 导入他人组件时：解压 → `requires` 合并进
  `~/Documents/Manchi/components/requirements.txt`（去重）→ 运行
  `install_deps.py` 自动安装缺失项。
- 安装失败（无网/需编译）标记为 `needs_setup`，运行前告警，不静默失败。

## 7. 导出 / 导入格式

- 导出：zip 整个 `<name>/` 文件夹（可含本组件 `requirements.txt`）。
- 导入：解压到 `components/<name>/` → 合并依赖到全局 `requirements.txt`
  → 自动安装 → 出现在组件列表。

## 8. 通用化铁律（保证"通用组件而非硬编码"）

1. 所有可变配置来自 `params`，禁止写死路径/阈值/关键词。
2. 所有产物写到 `artifacts_dir`，禁止写死绝对路径。
3. Secret 一律走 `params`（运行时注入）。
4. `run()` 为纯逻辑：不依赖全局状态，模块顶层不执行副作用。
5. 提供 `if __name__ == "__main__":` 自测块。

## 9. 组件运行失败的成因与红线（必读）

这些是"组件造出来却跑不起来"的真实坑，造组件时逐条对照：

1. **Excel/CSV 输入已是 `list[dict]`，再读文件必崩。**
   `input_requirement` 为 `excel`/`csv`/`table` 时，引擎已把源文件解析成
   行字典列表放进 `input_data`。组件若 `pd.read_excel(input_data)` 或
   `open(input_data)`，会因 `input_data` 是 `list`/`dict` 抛
   `FileNotFoundError`/`TypeError`。正确：直接遍历 `list[dict]`。
   （`file` 类型才是拿到路径，那时才自己读。）

2. **不要为"读输入"依赖 pandas/openpyxl。** 表格输入已是 `list[dict]`，
   纯 Python 可处理，组件通常 `requires: []`。仅"写出 Excel"才需
   `openpyxl` 并写进 `requires`。

3. **严禁模块顶层硬导入重型/未声明依赖。** `import pandas` 写顶部 → 运行时
   未装该包时 `exec_module` 直接 `ModuleNotFoundError`。改为 `run()` 内惰性
   `import`，并把用到的包写进 `requires`。

4. **manifest 严格合规**：`params` 是**对象**（按参数名索引），非数组；
   param `type` 仅限 `string|number|boolean|select|textarea|file`；必须有
   `display_name` 与 `source: "custom"`；文件夹名 == `manifest.name`。

5. **交付前必跑 `validate_component.py` 且零 ERROR，WARNING 也清零。**

> 口诀：**excel 进来是 list[dict]，别再读文件；重依赖放 run 里惰性 import；
> manifest 的 params 是对象不是数组。**


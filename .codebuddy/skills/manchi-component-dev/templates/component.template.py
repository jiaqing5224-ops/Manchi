"""
<display_name> - <一句话功能描述>

Component type: <transform|output|standalone|source>
Input requirement: <none|any|text|mail|excel|csv|docx|pdf|json|table|file>
Output: <描述返回的数据形状>
"""

from __future__ import annotations

from typing import Any


def run(params: dict, context: dict) -> Any:
    """执行组件逻辑。

    Args:
        params:  用户配置，键名对应 <name>.manifest.json 的 params
        context: {
            input_data,        # 上一步/输入源数据
            artifacts_dir,     # 产物目录（唯一稳定写位置）
            source_type, source_content, source_file_path,
            db,                # 可选
            llm_call,          # 可选：经配置端点的 LLM 调用
        }

    Returns:
        处理后数据（作为下一步 input_data）；output 类型透传 input_data。
    """
    # 1. 取参（全部来自 params，禁止硬编码）
    some_param = params.get("some_param", "默认值")

    # 2. 取上游数据
    data = context.get("input_data")

    # 3. 你的处理逻辑
    result = data  # TODO: 实现

    # 4. output 类型：把文件写到 artifacts_dir，并 return 透传数据
    # from pathlib import Path
    # out = Path(context["artifacts_dir"]) / "result.txt"
    # out.write_text(str(result), encoding="utf-8")

    return result


# 组件可独立运行自测
if __name__ == "__main__":
    sample_context = {
        "input_data": "hello world",
        "artifacts_dir": "/tmp",
    }
    print(run({"some_param": "x"}, sample_context))

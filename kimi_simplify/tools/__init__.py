"""
工具模块

什么是工具（Tool）？
工具是 Agent 用来和外部世界交互的方式
比如：读取文件、写入文件、执行命令、搜索网页等

为什么需要工具？
LLM 只能生成文本，不能直接操作计算机
通过工具，LLM 可以：
- 读取你的代码文件
- 修改你的代码
- 运行测试
- 搜索最新信息
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    """工具数据类"""
    name: str                           # 工具名称
    description: str                    # 工具描述
    parameters: dict                    # 参数定义
    fn: Callable[..., Any]              # 执行函数

    def to_openai_format(self) -> dict:
        """转换为 OpenAI API 需要的格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> Any:
        """执行工具

        **kwargs 表示接收任意数量的关键字参数
        比如：execute(path="file.txt", line_offset=1)
        """
        return self.fn(**kwargs)


class ToolRegistry:
    """工具注册表 - 管理所有可用的工具"""

    def __init__(self):
        """初始化空的工具字典"""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """列出所有工具"""
        return list(self._tools.values())

    def to_openai_format(self) -> list[dict]:
        """转换为 OpenAI 格式的工具列表"""
        return [tool.to_openai_format() for tool in self._tools.values()]


def create_default_registry() -> ToolRegistry:
    """创建默认的工具注册表"""
    from .builtins import create_registry
    return create_registry()

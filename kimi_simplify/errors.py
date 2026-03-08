"""
错误处理模块

这个模块定义了 Agent 系统中各种类型的错误，以及错误处理和重试机制。

为什么需要分类错误？
不同错误需要不同处理：
- 工具未找到：立即报错，重试无用
- 网络超时：可以重试
- 用户拒绝：特殊处理，需要暂停执行
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class KimiSimplifyError(Exception):
    """基础错误类"""
    pass


class ToolError(KimiSimplifyError):
    """工具相关错误的基类"""

    def __init__(self, message: str, *, brief: str = ""):
        super().__init__(message)
        self.message = message
        self.brief = brief or message


class ToolNotFoundError(ToolError):
    """工具未找到错误

    当 AI 请求调用一个不存在的工具时抛出。
    这通常是因为：
    1. 工具名称拼写错误
    2. 工具未正确注册
    3. AI 产生了幻觉（hallucination）
    """

    def __init__(self, tool_name: str):
        super().__init__(
            message=f"工具 '{tool_name}' 不存在。可用的工具可以通过 /tools 命令查看。",
            brief=f"工具 '{tool_name}' 不存在"
        )
        self.tool_name = tool_name


class ToolParseError(ToolError):
    """工具参数解析错误

    当 AI 提供的参数格式不正确时抛出。
    比如：
    - 缺少必需参数
    - 参数类型错误（字符串传给了数字参数）
    - JSON 格式错误
    """

    def __init__(self, tool_name: str, param_name: str, reason: str):
        super().__init__(
            message=f"工具 '{tool_name}' 的参数 '{param_name}' 解析失败：{reason}",
            brief=f"参数解析失败"
        )
        self.tool_name = tool_name
        self.param_name = param_name
        self.reason = reason


class ToolExecutionError(ToolError):
    """工具执行错误

    工具函数执行时抛出的异常。
    这是最通用的执行错误。
    """

    def __init__(self, tool_name: str, original_error: Exception):
        super().__init__(
            message=f"工具 '{tool_name}' 执行失败：{original_error}",
            brief=f"执行失败：{type(original_error).__name__}"
        )
        self.tool_name = tool_name
        self.original_error = original_error


class ToolTimeoutError(ToolError):
    """工具执行超时

    当工具执行时间超过设定限制时抛出。
    这种错误通常可以重试。
    """

    def __init__(self, tool_name: str, timeout: float):
        super().__init__(
            message=f"工具 '{tool_name}' 执行超时（限制 {timeout} 秒）。可能是操作太复杂或网络延迟。",
            brief=f"执行超时（{timeout}s）"
        )
        self.tool_name = tool_name
        self.timeout = timeout


class ToolRejectedError(ToolError):
    """工具被用户拒绝

    当用户选择不执行某个工具时抛出。
    这不是真正的"错误"，而是用户的主动选择。
    """

    def __init__(self):
        super().__init__(
            message="用户拒绝了此工具调用。请遵循用户的新指示。",
            brief="用户已拒绝"
        )


@dataclass
class ToolResult:
    """
    工具执行结果

    统一的结果格式，包含：
    - success: 是否成功
    - output: 主要输出内容
    - message: 状态消息
    - is_error: 是否是错误结果
    - error_type: 错误类型（如果有）
    """
    success: bool
    output: str
    message: str = ""
    is_error: bool = False
    error_type: str | None = None

    @staticmethod
    def ok(output: str, message: str = "") -> "ToolResult":
        """创建成功的结果"""
        return ToolResult(
            success=True,
            output=output,
            message=message or "执行成功",
            is_error=False
        )

    @staticmethod
    def error(error_msg: str, error_type: str = "execution_error") -> "ToolResult":
        """创建错误的结果"""
        return ToolResult(
            success=False,
            output="",
            message=error_msg,
            is_error=True,
            error_type=error_type
        )

    def to_message_content(self) -> str:
        """转换为消息内容格式"""
        if self.is_error:
            return f"Error ({self.error_type}): {self.message}"

        content = self.output
        if self.message:
            content = f"[{self.message}]\n{content}"
        return content


def classify_error(error: Exception, tool_name: str = "") -> ToolResult:
    """
    将异常分类为 ToolResult

    这是一个智能错误分类器，根据异常类型返回不同的结果。

    参数：
        error: 捕获到的异常
        tool_name: 发生错误的工具名称

    返回值：
        ToolResult 对象
    """
    if isinstance(error, ToolNotFoundError):
        return ToolResult.error(error.message, "tool_not_found")

    elif isinstance(error, ToolParseError):
        return ToolResult.error(error.message, "parse_error")

    elif isinstance(error, ToolTimeoutError):
        return ToolResult.error(error.message, "timeout")

    elif isinstance(error, ToolRejectedError):
        return ToolResult.error(error.message, "user_rejected")

    elif isinstance(error, ToolError):
        return ToolResult.error(error.message, "tool_error")

    elif isinstance(error, FileNotFoundError):
        return ToolResult.error(f"文件未找到：{error}", "file_not_found")

    elif isinstance(error, PermissionError):
        return ToolResult.error(f"权限不足：{error}", "permission_denied")

    elif isinstance(error, TimeoutError):
        return ToolResult.error(
            f"操作超时。如果这是网络请求，请检查连接或稍后重试。",
            "timeout"
        )

    else:
        # 未知错误
        error_type = type(error).__name__
        return ToolResult.error(
            f"工具执行出错 [{error_type}]: {error}",
            "unknown_error"
        )

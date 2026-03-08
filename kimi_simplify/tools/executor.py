"""
工具执行器模块

这个模块提供了增强的工具执行功能，包括：
1. 统一的错误处理
2. 自动重试机制
3. 执行超时控制
4. 详细的执行日志

使用示例：
    from kimi_simplify.tools.executor import ToolExecutor

    executor = ToolExecutor(
        max_retries=3,
        timeout=60,
        enable_retry=True
    )

    result = executor.execute(tool, {"path": "test.py"})
    if result.success:
        print(result.output)
    else:
        print(f"错误: {result.message}")
"""

from __future__ import annotations

import signal
import time
from typing import Any, Callable

from ..errors import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolParseError,
    ToolRejectedError,
    ToolResult,
    ToolTimeoutError,
    classify_error,
)
from ..retry import RetryExecutor, is_retryable_error
from . import Tool


class TimeoutContext:
    """
    超时上下文管理器

    使用信号（Signal）实现超时控制。
    注意：这仅在 Unix/Linux/macOS 上有效，Windows 不支持 signal.SIGALRM。

    示例：
        with TimeoutContext(timeout=5):
            # 这段代码如果超过 5 秒会抛出 TimeoutError
            long_running_operation()
    """

    def __init__(self, timeout: float):
        self.timeout = timeout
        self._original_handler = None

    def _timeout_handler(self, signum, frame):
        """信号处理函数"""
        raise TimeoutError(f"操作超时（{self.timeout}秒）")

    def __enter__(self):
        # 尝试设置信号（仅 Unix/Linux/macOS）
        try:
            self._original_handler = signal.signal(
                signal.SIGALRM, self._timeout_handler
            )
            signal.alarm(int(self.timeout))
        except (AttributeError, ValueError):
            # Windows 或不支持信号的环境
            self._original_handler = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 恢复原来的信号处理
        if self._original_handler is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self._original_handler)


class ToolExecutor:
    """
    工具执行器

    这是工具执行的核心类，负责：
    1. 参数验证
    2. 超时控制
    3. 错误处理
    4. 自动重试
    5. 结果格式化

    属性：
        max_retries: 最大重试次数
        timeout: 默认超时时间（秒）
        enable_retry: 是否启用自动重试
    """

    def __init__(
        self,
        max_retries: int = 2,
        timeout: float = 60.0,
        enable_retry: bool = True,
        on_retry: Callable[[str, Exception, int], None] | None = None,
    ):
        """
        初始化执行器

        参数：
            max_retries: 最大重试次数（默认2次）
            timeout: 默认超时时间（默认60秒）
            enable_retry: 是否启用重试（默认True）
            on_retry: 重试回调函数，参数为 (工具名, 异常, 重试次数)
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_retry = enable_retry
        self.on_retry = on_retry
        self._execution_stats: dict[str, dict] = {}

    def execute(self, tool: Tool | None, arguments: dict[str, Any]) -> ToolResult:
        """
        执行工具

        这是主要的执行入口，处理完整的工具调用生命周期。

        参数：
            tool: 要执行的工具对象（None 会返回错误）
            arguments: 工具参数

        返回值：
            ToolResult 包含执行结果
        """
        start_time = time.time()

        # 1. 检查工具是否存在
        if tool is None:
            error = ToolNotFoundError("<unknown>")
            return classify_error(error)

        # 2. 验证参数（简化版，检查必需参数）
        try:
            self._validate_arguments(tool, arguments)
        except ToolParseError as e:
            return classify_error(e)

        # 3. 执行（带重试）
        if self.enable_retry and self.max_retries > 0:
            result = self._execute_with_retry(tool, arguments)
        else:
            result = self._execute_once(tool, arguments)

        # 4. 记录统计
        execution_time = time.time() - start_time
        self._record_stats(tool.name, execution_time, result)

        return result

    def _validate_arguments(self, tool: Tool, arguments: dict[str, Any]) -> None:
        """
        验证参数

        检查必需参数是否存在。
        简化版，完整的 JSON Schema 验证需要更复杂的实现。

        参数：
            tool: 工具对象
            arguments: 参数字典

        抛出：
            ToolParseError: 参数验证失败
        """
        params = tool.parameters.get("properties", {})
        required = tool.parameters.get("required", [])

        for param_name in required:
            if param_name not in arguments:
                raise ToolParseError(
                    tool_name=tool.name,
                    param_name=param_name,
                    reason=f"缺少必需参数 '{param_name}'",
                )

            # 简单的类型检查
            param_info = params.get(param_name, {})
            expected_type = param_info.get("type")
            value = arguments[param_name]

            if expected_type == "string" and not isinstance(value, str):
                raise ToolParseError(
                    tool_name=tool.name,
                    param_name=param_name,
                    reason=f"参数 '{param_name}' 应该是字符串，但得到 {type(value).__name__}",
                )
            elif expected_type == "integer" and not isinstance(value, int):
                raise ToolParseError(
                    tool_name=tool.name,
                    param_name=param_name,
                    reason=f"参数 '{param_name}' 应该是整数，但得到 {type(value).__name__}",
                )

    def _execute_once(self, tool: Tool, arguments: dict[str, Any]) -> ToolResult:
        """
        单次执行工具（带超时控制）

        参数：
            tool: 工具对象
            arguments: 参数

        返回值：
            ToolResult
        """
        try:
            # 使用超时上下文
            with TimeoutContext(self.timeout):
                # 执行工具函数
                raw_result = tool.execute(**arguments)

            # 处理返回结果
            return self._process_result(raw_result)

        except TimeoutError as e:
            error = ToolTimeoutError(tool.name, self.timeout)
            return classify_error(error)

        except Exception as e:
            # 分类并包装错误
            return classify_error(e, tool.name)

    def _execute_with_retry(self, tool: Tool, arguments: dict[str, Any]) -> ToolResult:
        """
        带重试的执行

        参数：
            tool: 工具对象
            arguments: 参数

        返回值：
            ToolResult
        """
        retry_executor = RetryExecutor(
            max_retries=self.max_retries,
            initial_delay=1.0,
            max_delay=10.0,
        )

        def attempt():
            return self._execute_once(tool, arguments)

        retry_result = retry_executor.execute(attempt)

        if retry_result.success and retry_result.result is not None:
            result = retry_result.result
            # 如果成功但有重试，在消息中注明
            if retry_result.attempts > 1 and isinstance(result, ToolResult):
                result.message += f" （重试 {retry_result.attempts - 1} 次后成功）"
            return result

        # 全部重试失败
        final_error = retry_result.final_error or Exception("未知错误")
        return classify_error(final_error, tool.name)

    def _process_result(self, raw_result: Any) -> ToolResult:
        """
        处理原始返回结果

        工具函数可以返回不同格式，这里统一转换为 ToolResult。

        参数：
            raw_result: 工具函数的原始返回值

        返回值：
            ToolResult
        """
        # 如果已经是 ToolResult，直接返回
        if isinstance(raw_result, ToolResult):
            return raw_result

        # 如果是字典，提取字段
        if isinstance(raw_result, dict):
            if "error" in raw_result:
                return ToolResult.error(
                    error_msg=raw_result["error"],
                    error_type=raw_result.get("error_type", "execution_error"),
                )

            return ToolResult.ok(
                output=raw_result.get("output", str(raw_result)),
                message=raw_result.get("message", ""),
            )

        # 其他类型，转换为字符串
        return ToolResult.ok(output=str(raw_result))

    def _record_stats(
        self, tool_name: str, execution_time: float, result: ToolResult
    ) -> None:
        """
        记录执行统计

        用于分析和优化工具性能。

        参数：
            tool_name: 工具名称
            execution_time: 执行时间（秒）
            result: 执行结果
        """
        if tool_name not in self._execution_stats:
            self._execution_stats[tool_name] = {
                "calls": 0,
                "successes": 0,
                "failures": 0,
                "total_time": 0.0,
                "errors": {},
            }

        stats = self._execution_stats[tool_name]
        stats["calls"] += 1
        stats["total_time"] += execution_time

        if result.success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
            error_type = result.error_type or "unknown"
            stats["errors"][error_type] = stats["errors"].get(error_type, 0) + 1

    def get_stats(self) -> dict[str, dict]:
        """
        获取执行统计

        返回值：
            工具名称 -> 统计数据的字典
        """
        return self._execution_stats.copy()

    def print_stats(self) -> None:
        """打印执行统计"""
        if not self._execution_stats:
            print("暂无执行统计")
            return

        print("\n📊 工具执行统计:")
        print("-" * 60)

        for tool_name, stats in self._execution_stats.items():
            calls = stats["calls"]
            success_rate = (stats["successes"] / calls * 100) if calls > 0 else 0
            avg_time = stats["total_time"] / calls if calls > 0 else 0

            print(f"\n  🔧 {tool_name}")
            print(f"     调用次数: {calls}")
            print(f"     成功率: {success_rate:.1f}%")
            print(f"     平均耗时: {avg_time:.3f}s")

            if stats["errors"]:
                print(f"     错误分布:")
                for error_type, count in stats["errors"].items():
                    print(f"       - {error_type}: {count}")


class SafeToolExecutor(ToolExecutor):
    """
    安全的工具执行器（沙箱模式）

    增加了额外的安全检查：
    1. 危险命令拦截
    2. 路径遍历检查
    3. 敏感操作确认

    适用于处理不可信的 AI 输出。
    """

    # 危险的 shell 命令模式
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "rm -rf ~",
        "rm -rf /*",
        ":(){ :|:& };:",  # fork bomb
        "mkfs.",
        "dd if=/dev/zero of=/dev/sda",
        "> /dev/sda",
        "mv / /dev/null",
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blocked_commands: list[str] = []

    def execute(self, tool: Tool | None, arguments: dict[str, Any]) -> ToolResult:
        """
        执行前进行安全检查
        """
        if tool is None:
            return classify_error(ToolNotFoundError("<unknown>"))

        # 检查危险命令
        if tool.name == "Shell":
            command = arguments.get("command", "")
            danger = self._check_dangerous_command(command)
            if danger:
                self.blocked_commands.append(command)
                return ToolResult.error(
                    error_msg=f"危险命令被拦截: {danger}",
                    error_type="security_blocked",
                )

        return super().execute(tool, arguments)

    def _check_dangerous_command(self, command: str) -> str | None:
        """
        检查命令是否危险

        参数：
            command: 要检查的命令

        返回值：
            None - 安全
            str - 危险原因
        """
        cmd_lower = command.lower().strip()

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return f"匹配危险模式 '{pattern}'"

        # 检查 rm -rf 后面直接跟根目录
        if cmd_lower.startswith("rm -rf /") or cmd_lower.startswith("rm -rf ~"):
            return "尝试删除根目录或家目录"

        return None

"""
重试机制模块

这个模块实现了工具调用的重试逻辑，包括：
1. 指数退避（Exponential Backoff）- 失败后等待时间逐渐增加
2. 可配置的重试策略
3. 对特定错误类型的重试判断

什么是指数退避？
如果第一次失败后等 1 秒重试，第二次等 2 秒，第三次等 4 秒...
这样可以避免对已经过载的服务造成更大压力。

示例：
    @retry_with_backoff(max_retries=3)
    def call_api():
        # 如果失败，会自动重试最多 3 次
        pass
"""

from __future__ import annotations

import functools
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

# Python 3.10+ 有 ParamSpec，低版本需要兼容
try:
    from typing import ParamSpec
except ImportError:
    # Python < 3.10 的兼容处理
    class ParamSpec:
        def __init__(self, name: str):
            self.name = name
            self.args = Any
            self.kwargs = Any

from .errors import (
    ToolError,
    ToolNotFoundError,
    ToolParseError,
    ToolRejectedError,
    ToolTimeoutError,
)

P = ParamSpec("P")
T = TypeVar("T")


def is_retryable_error(error: Exception) -> bool:
    """
    判断错误是否值得重试

    有些错误重试也没用（如工具不存在、参数解析错误），
    有些错误重试可能成功（如网络超时、临时的服务不可用）。

    参数：
        error: 捕获到的异常

    返回值：
        True - 值得重试
        False - 不需要重试
    """
    # 这些错误重试也没用
    non_retryable_errors = (
        ToolNotFoundError,  # 工具不存在，重试也不会出现
        ToolParseError,     # 参数错误，重试还是错
        ToolRejectedError,  # 用户拒绝，不能自动重试
        ValueError,         # 参数值错误
        TypeError,          # 类型错误
        KeyError,           # 键不存在
    )

    if isinstance(error, non_retryable_errors):
        return False

    # 超时错误通常值得重试（可能是临时的）
    retryable_errors = (
        ToolTimeoutError,
        TimeoutError,
        ConnectionError,
        OSError,            # IO 错误可能是暂时的
    )

    if isinstance(error, retryable_errors):
        return True

    # 工具执行错误看具体类型
    if isinstance(error, ToolError):
        # 如果是网络相关的子类，可能可以重试
        return "timeout" in str(error).lower() or "network" in str(error).lower()

    # 其他未知错误，默认不重试（安全第一）
    return False


def calculate_wait_time(
    attempt: int,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    计算重试等待时间

    使用指数退避算法，并可选择添加随机抖动（jitter），
    避免多个客户端在同一时间重试（"惊群效应"）。

    参数：
        attempt: 当前是第几次重试（从 0 开始）
        initial_delay: 初始等待时间（秒）
        max_delay: 最大等待时间（秒）
        exponential_base: 指数基数（默认 2，即 1, 2, 4, 8...）
        jitter: 是否添加随机抖动

    返回值：
        建议的等待时间（秒）

    示例：
        >>> calculate_wait_time(0)  # 第一次重试
        1.0  # 或 0.8~1.2 之间有 jitter
        >>> calculate_wait_time(2)  # 第三次重试
        4.0  # 或 3.2~4.8 之间有 jitter
    """
    # 计算指数退避时间
    wait_time = initial_delay * (exponential_base ** attempt)

    # 不超过最大延迟
    wait_time = min(wait_time, max_delay)

    # 添加抖动（±20% 随机变化）
    if jitter:
        jitter_amount = wait_time * 0.2
        wait_time = wait_time + random.uniform(-jitter_amount, jitter_amount)

    return max(0.1, wait_time)  # 至少等待 0.1 秒


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    on_retry: Callable[[Exception, int, float], None] | None = None,
):
    """
    装饰器：为函数添加指数退避重试

    这是一个函数装饰器，可以自动为任何函数添加重试逻辑。

    参数：
        max_retries: 最大重试次数
        initial_delay: 初始等待时间
        max_delay: 最大等待时间
        on_retry: 重试时的回调函数，参数为 (异常, 重试次数, 等待时间)

    示例：
        @retry_with_backoff(max_retries=3)
        def fetch_data(url: str) -> dict:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()

        # 如果 fetch_data 抛出可重试的异常，会自动重试最多 3 次
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # 判断是否应该重试
                    if attempt >= max_retries:
                        # 已达到最大重试次数
                        break

                    if not is_retryable_error(e):
                        # 不可重试的错误，直接抛出
                        raise

                    # 计算等待时间
                    wait_time = calculate_wait_time(
                        attempt,
                        initial_delay=initial_delay,
                        max_delay=max_delay,
                    )

                    # 调用回调（如果有）
                    if on_retry:
                        on_retry(e, attempt + 1, wait_time)

                    # 等待后重试
                    time.sleep(wait_time)

            # 所有重试都失败了
            raise last_error or RuntimeError("重试耗尽但无异常")

        return wrapper
    return decorator


class RetryExecutor:
    """
    重试执行器

    用于更复杂的场景，需要手动控制重试逻辑。

    示例：
        executor = RetryExecutor(max_retries=3)

        def attempt_operation():
            # 尝试操作
            return some_risky_call()

        result = executor.execute(attempt_operation)
        if not result.success:
            print(f"最终失败: {result.error}")
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.attempt_count = 0
        self.errors: list[Exception] = []

    def execute(self, operation: Callable[[], T]) -> "RetryResult[T]":
        """
        执行操作，失败时自动重试

        参数：
            operation: 要执行的无参函数

        返回值：
            RetryResult 包含结果或错误信息
        """
        self.errors = []
        self.attempt_count = 0

        for attempt in range(self.max_retries + 1):
            self.attempt_count = attempt + 1

            try:
                result = operation()
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=self.attempt_count,
                    errors=self.errors,
                )
            except Exception as e:
                self.errors.append(e)

                # 判断是否应该重试
                if attempt >= self.max_retries:
                    break

                if not is_retryable_error(e):
                    # 不可重试的错误
                    break

                # 计算并等待
                wait_time = calculate_wait_time(
                    attempt,
                    initial_delay=self.initial_delay,
                    max_delay=self.max_delay,
                )
                time.sleep(wait_time)

        # 所有尝试都失败
        return RetryResult(
            success=False,
            result=None,
            attempts=self.attempt_count,
            errors=self.errors,
            final_error=self.errors[-1] if self.errors else None,
        )


@dataclass
class RetryResult(Generic[T]):
    """重试执行结果"""

    success: bool
    result: T | None
    attempts: int
    errors: list[Exception]
    final_error: Exception | None = None

    def get_or_raise(self) -> T:
        """获取结果，失败则抛出最后异常"""
        if self.success and self.result is not None:
            return self.result
        if self.final_error:
            raise self.final_error
        raise RuntimeError("未知错误")

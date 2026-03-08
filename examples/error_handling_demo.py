"""
错误处理演示脚本

这个脚本展示了 kimi-simplify 的错误处理功能，包括：
1. 不同类型的错误分类
2. 自动重试机制
3. 超时控制
4. 错误统计

运行方式:
    cd /Users/zheisenbergy/code/agent/kimi-cli-simplify
    python -m examples.error_handling_demo
"""

from __future__ import annotations

import sys
sys.path.insert(0, "/Users/zheisenbergy/code/agent/kimi-cli-simplify")

from kimi_simplify.errors import (
    ToolNotFoundError,
    ToolParseError,
    ToolExecutionError,
    ToolTimeoutError,
    ToolResult,
    classify_error,
)
from kimi_simplify.retry import (
    retry_with_backoff,
    calculate_wait_time,
    is_retryable_error,
)
from kimi_simplify.tools.executor import ToolExecutor, SafeToolExecutor


def demo_error_types():
    """演示各种错误类型"""
    print("=" * 60)
    print("📚 错误类型演示")
    print("=" * 60)

    # 1. 工具未找到错误
    print("\n1. ToolNotFoundError（工具不存在）")
    print("-" * 40)
    error = ToolNotFoundError("ReadPDF")
    result = classify_error(error)
    print(f"  错误信息: {result.message}")
    print(f"  错误类型: {result.error_type}")
    print(f"  是否成功: {result.success}")

    # 2. 参数解析错误
    print("\n2. ToolParseError（参数解析失败）")
    print("-" * 40)
    error = ToolParseError("ReadFile", "path", "缺少必需参数")
    result = classify_error(error)
    print(f"  错误信息: {result.message}")
    print(f"  错误类型: {result.error_type}")

    # 3. 超时错误
    print("\n3. ToolTimeoutError（执行超时）")
    print("-" * 40)
    error = ToolTimeoutError("Shell", 60.0)
    result = classify_error(error)
    print(f"  错误信息: {result.message}")
    print(f"  错误类型: {result.error_type}")

    # 4. 执行错误
    print("\n4. ToolExecutionError（执行异常）")
    print("-" * 40)
    error = ToolExecutionError("WriteFile", PermissionError("权限不足"))
    result = classify_error(error)
    print(f"  错误信息: {result.message}")
    print(f"  错误类型: {result.error_type}")


def demo_retry_logic():
    """演示重试逻辑"""
    print("\n" + "=" * 60)
    print("🔄 重试逻辑演示")
    print("=" * 60)

    # 1. 指数退避计算
    print("\n1. 指数退避等待时间计算")
    print("-" * 40)
    for i in range(5):
        wait_time = calculate_wait_time(i, initial_delay=1.0, jitter=False)
        print(f"  第 {i+1} 次重试: 等待 {wait_time:.1f} 秒")

    # 2. 可重试错误判断
    print("\n2. 可重试错误判断")
    print("-" * 40)
    errors = [
        ToolNotFoundError("Test"),
        ToolParseError("Test", "param", "bad"),
        ToolTimeoutError("Test", 30),
        TimeoutError(),
        ValueError("bad value"),
    ]
    for error in errors:
        retryable = is_retryable_error(error)
        status = "✅ 可重试" if retryable else "❌ 不可重试"
        print(f"  {type(error).__name__:25} {status}")


def demo_executor():
    """演示工具执行器"""
    print("\n" + "=" * 60)
    print("⚙️ 工具执行器演示")
    print("=" * 60)

    from kimi_simplify.tools import Tool, ToolRegistry

    # 创建测试工具
    def risky_tool(fail: bool = False) -> dict:
        if fail:
            raise ConnectionError("网络连接失败")
        return {"output": "操作成功"}

    registry = ToolRegistry()
    registry.register(Tool(
        name="RiskyTool",
        description="A tool that might fail",
        parameters={
            "type": "object",
            "properties": {
                "fail": {"type": "boolean", "default": False}
            }
        },
        fn=risky_tool
    ))

    tool = registry.get("RiskyTool")

    # 1. 正常执行
    print("\n1. 正常执行")
    print("-" * 40)
    executor = ToolExecutor(max_retries=0)
    result = executor.execute(tool, {"fail": False})
    print(f"  成功: {result.success}")
    print(f"  输出: {result.output}")

    # 2. 失败后重试
    print("\n2. 失败重试（模拟网络错误）")
    print("-" * 40)
    executor = ToolExecutor(max_retries=3, enable_retry=True)

    # 使用一个会失败的工具
    def always_fail():
        raise TimeoutError("连接超时")

    registry2 = ToolRegistry()
    registry2.register(Tool(
        name="FailTool",
        description="Always fails",
        parameters={"type": "object", "properties": {}},
        fn=always_fail
    ))

    fail_tool = registry2.get("FailTool")
    result = executor.execute(fail_tool, {})
    print(f"  成功: {result.success}")
    print(f"  错误: {result.message}")
    print(f"  类型: {result.error_type}")

    # 3. 显示统计
    print("\n3. 执行统计")
    print("-" * 40)
    executor.print_stats()


def demo_safe_executor():
    """演示安全执行器（危险命令拦截）"""
    print("\n" + "=" * 60)
    print("🛡️ 安全执行器演示（危险命令拦截）")
    print("=" * 60)

    from kimi_simplify.tools import Tool, ToolRegistry

    def shell_tool(command: str) -> dict:
        return {"output": f"Executed: {command}"}

    registry = ToolRegistry()
    registry.register(Tool(
        name="Shell",
        description="Execute shell commands",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"]
        },
        fn=shell_tool
    ))

    tool = registry.get("Shell")

    # 使用安全执行器
    safe_executor = SafeToolExecutor()

    # 测试危险命令
    dangerous_commands = [
        "ls -la",
        "rm -rf /",
        "rm -rf ~",
        "cat file.txt",
    ]

    for cmd in dangerous_commands:
        result = safe_executor.execute(tool, {"command": cmd})
        status = "❌ 拦截" if result.is_error else "✅ 允许"
        print(f"  {status} {cmd[:30]:30}")
        if result.is_error:
            print(f"       原因: {result.message}")


def main():
    """主函数"""
    print("\n" + "🌟" * 30)
    print("  kimi-simplify 错误处理功能演示")
    print("🌟" * 30)

    try:
        demo_error_types()
        demo_retry_logic()
        demo_executor()
        demo_safe_executor()

        print("\n" + "=" * 60)
        print("✅ 所有演示完成!")
        print("=" * 60)
        print("\n💡 这些功能已集成到 KimiSoul 中:")
        print("   - 自动错误分类")
        print("   - 智能重试（仅对可重试错误）")
        print("   - 超时控制")
        print("   - 执行统计")
        print("   - 危险命令拦截（可选）")

    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

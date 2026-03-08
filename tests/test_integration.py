"""集成测试 - 完整流程测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kimi_simplify.config import Config, LLMConfig
from kimi_simplify.soul import Runtime, Agent
from kimi_simplify.soul.kimisoul import KimiSoul


def test_full_flow():
    """测试完整流程（需要 API Key）"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  跳过测试: 未设置 OPENAI_API_KEY")
        print("   请运行: export OPENAI_API_KEY='your-key'")
        return

    print("创建 Runtime...")
    config = Config(
        llm=LLMConfig(
            api_key=api_key,
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.moonshot.cn/v1"),
            model="kimi-k2.5",
        ),
    )
    runtime = Runtime.create(config)

    print("创建 Agent...")
    agent = Agent.create(runtime)

    print("创建 Soul...")
    soul = KimiSoul(agent)

    print("\n开始对话测试:\n")

    # 测试 1: 简单对话
    print("测试 1: 简单对话")
    print("-" * 40)
    result = soul.run_turn("你好，请用一句话介绍自己")
    if result.success:
        print(f"✅ 成功 ({result.step_count} 步)")
        print(f"回复: {result.message[:100]}...")
    else:
        print(f"❌ 失败: {result.message}")

    print()

    # 测试 2: 工具调用
    print("测试 2: 工具调用（列出当前目录）")
    print("-" * 40)
    result = soul.run_turn("请使用 Shell 工具执行 'ls -la' 命令")
    if result.success:
        print(f"✅ 成功 ({result.step_count} 步)")
        if result.step_count > 1:
            print("   (使用了工具)")
    else:
        print(f"❌ 失败: {result.message}")

    print()

    # 测试 3: 文件操作
    print("测试 3: 文件操作")
    print("-" * 40)

    # 先创建一个测试文件
    test_file = "/tmp/kimi_test.txt"
    with open(test_file, "w") as f:
        f.write("Hello Kimi!")

    result = soul.run_turn(f"请读取文件 {test_file}")
    if result.success:
        print(f"✅ 成功 ({result.step_count} 步)")
        if "Hello Kimi" in result.message:
            print("   (正确读取了文件内容)")
    else:
        print(f"❌ 失败: {result.message}")

    # 清理
    os.remove(test_file)

    print("\n✅ 集成测试完成!")


if __name__ == "__main__":
    test_full_flow()

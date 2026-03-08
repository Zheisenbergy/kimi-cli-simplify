"""Soul 测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kimi_simplify.config import Config, LLMConfig
from kimi_simplify.soul import Runtime, Agent
from kimi_simplify.soul.kimisoul import KimiSoul


def test_runtime_creation():
    """测试 Runtime 创建"""
    config = Config(
        llm=LLMConfig(api_key="fake-key", base_url="https://api.moonshot.cn/v1"),
    )

    runtime = Runtime.create(config)

    assert runtime.config == config
    assert runtime.llm is not None
    assert runtime.session is not None
    assert runtime.tool_registry is not None

    print("✅ test_runtime_creation 通过")


def test_agent_creation():
    """测试 Agent 创建"""
    config = Config(
        llm=LLMConfig(api_key="fake-key"),
    )

    runtime = Runtime.create(config)
    agent = Agent.create(runtime)

    assert agent.name == "kimi-simplify"
    assert agent.runtime == runtime
    assert len(agent.system_prompt) > 0

    print("✅ test_agent_creation 通过")


def test_soul_creation():
    """测试 Soul 创建"""
    config = Config(
        llm=LLMConfig(api_key="fake-key"),
    )

    runtime = Runtime.create(config)
    agent = Agent.create(runtime)
    soul = KimiSoul(agent)

    assert soul._agent == agent
    assert len(soul._messages) == 1  # 系统提示
    assert soul._messages[0].role == "system"

    print("✅ test_soul_creation 通过")


def test_soul_history():
    """测试 Soul 历史记录"""
    config = Config(
        llm=LLMConfig(api_key="fake-key"),
    )

    runtime = Runtime.create(config)
    agent = Agent.create(runtime)
    soul = KimiSoul(agent)

    # 初始只有系统消息
    assert len(soul.get_history()) == 1

    # 清空历史
    soul.clear_history()
    assert len(soul.get_history()) == 1  # 系统消息保留

    print("✅ test_soul_history 通过")


if __name__ == "__main__":
    print("运行 Soul 测试...\n")
    test_runtime_creation()
    test_agent_creation()
    test_soul_creation()
    test_soul_history()
    print("\n✅ 所有 Soul 测试通过!")

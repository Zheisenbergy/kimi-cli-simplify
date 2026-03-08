"""LLM 测试 - 需要设置 API Key"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kimi_simplify.llm import LLM, Message


def test_llm_basic():
    """测试基本对话（需要 API Key）"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  跳过测试: 未设置 OPENAI_API_KEY")
        return

    llm = LLM(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.moonshot.cn/v1"),
        model="kimi-k2.5",
    )

    messages = [Message(role="user", content="你好，请用一句话介绍自己")]
    response = llm.chat(messages)

    assert response.role == "assistant"
    assert len(response.content) > 0
    print(f"✅ LLM 响应: {response.content[:50]}...")


def test_llm_with_tools():
    """测试工具调用（需要 API Key）"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  跳过测试: 未设置 OPENAI_API_KEY")
        return

    llm = LLM(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.moonshot.cn/v1"),
        model="kimi-k2.5",
    )

    # 定义一个简单工具
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    }]

    messages = [Message(role="user", content="北京今天天气怎么样？")]
    response = llm.chat(messages, tools=tools)

    print(f"✅ LLM 响应: {response.content[:50]}...")
    if response.tool_calls:
        print(f"   工具调用: {response.tool_calls[0].name}")
        print(f"   参数: {response.tool_calls[0].arguments}")


if __name__ == "__main__":
    print("运行 LLM 测试...\n")
    test_llm_basic()
    print()
    test_llm_with_tools()
    print("\n✅ LLM 测试完成!")

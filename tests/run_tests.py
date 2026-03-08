#!/usr/bin/env python3
"""测试运行器"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Kimi CLI Simplify - 测试套件")
    print("=" * 60)
    print()

    # 1. 工具测试（不需要 API Key）
    print("【1/4】工具测试")
    print("-" * 60)
    try:
        from test_tools import (
            test_read_file,
            test_write_file,
            test_str_replace,
            test_shell,
            test_glob,
            test_grep,
        )
        test_read_file()
        test_write_file()
        test_str_replace()
        test_shell()
        test_glob()
        test_grep()
        print("✅ 工具测试全部通过\n")
    except Exception as e:
        print(f"❌ 工具测试失败: {e}\n")
        return False

    # 2. Soul 测试（不需要 API Key）
    print("【2/4】Soul 测试")
    print("-" * 60)
    try:
        from test_soul import (
            test_runtime_creation,
            test_agent_creation,
            test_soul_creation,
            test_soul_history,
        )
        test_runtime_creation()
        test_agent_creation()
        test_soul_creation()
        test_soul_history()
        print("✅ Soul 测试全部通过\n")
    except Exception as e:
        print(f"❌ Soul 测试失败: {e}\n")
        return False

    # 3. LLM 测试（需要 API Key）
    print("【3/4】LLM 测试")
    print("-" * 60)
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  跳过: 未设置 OPENAI_API_KEY\n")
    else:
        try:
            from test_llm import test_llm_basic, test_llm_with_tools
            test_llm_basic()
            print()
            test_llm_with_tools()
            print("✅ LLM 测试全部通过\n")
        except Exception as e:
            print(f"❌ LLM 测试失败: {e}\n")
            return False

    # 4. 集成测试（需要 API Key）
    print("【4/4】集成测试")
    print("-" * 60)
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  跳过: 未设置 OPENAI_API_KEY\n")
    else:
        try:
            from test_integration import test_full_flow
            test_full_flow()
            print()
        except Exception as e:
            print(f"❌ 集成测试失败: {e}\n")
            return False

    print("=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

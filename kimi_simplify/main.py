#!/usr/bin/env python3
"""
Kimi CLI Simplify - 主程序入口

这是程序的入口文件，负责：
1. 加载配置（API Key 等）
2. 创建必要的对象（Runtime、Agent、KimiSoul）
3. 运行主循环，处理用户输入
4. 调用压缩功能（当对话太长时）

什么是 Agent？
Agent（智能体）是一个能自主决策的 AI 系统。
与普通聊天机器人不同，Agent 可以：
- 使用工具（读取文件、执行命令等）
- 多轮思考（尝试 → 失败 → 再尝试）
- 记住上下文（之前的对话历史）

程序架构：
main() → 创建对象 → 主循环 → 处理输入 → 调用 Agent → 返回结果
"""

from __future__ import annotations

import sys
from pathlib import Path

# 从其他模块导入需要的类和函数
from .config import load_config_from_env
from .soul import Agent, Runtime
from .soul.kimisoul import KimiSoul


def print_welcome():
    """
    打印欢迎信息

    使用多行字符串定义 ASCII 艺术字
    让用户知道程序已启动
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║              🌙 Kimi CLI Simplify                            ║
║                                                              ║
║  参考 MoonshotAI/kimi-cli 架构的简化版实现                      ║
║                                                              ║
║  ✨ 特性: 流式输出 | 会话持久化 | Web搜索 | 上下文压缩            ║
║                                                              ║
║  可用命令:                                                   ║
║    /help       - 显示帮助                                     ║
║    /tools      - 显示可用工具                                 ║
║    /clear      - 清空对话历史                                 ║
║    /save       - 保存会话                                     ║
║    /load       - 加载会话                                     ║
║    /compact    - 简单压缩上下文                               ║
║    /compact-ai - 智能压缩（使用 AI，效果更好但有成本）           ║
║    /stats      - 显示上下文统计                               ║
║    /quit       - 退出                                        ║
╚══════════════════════════════════════════════════════════════╝
""")


def print_help():
    """
    打印帮助信息

    解释每个命令的用途
    """
    print("""
可用命令:
  /help       - 显示此帮助信息
  /tools      - 显示所有可用工具及其说明
  /clear      - 清空对话历史（保留系统提示）
  /save       - 保存当前会话到 .kimi_session.json
  /load       - 从 .kimi_session.json 加载会话
  /compact    - 简单压缩上下文（规则-based，免费）
  /compact-ai - 智能压缩（AI-based，效果更好但有 API 成本）
  /stats      - 显示当前上下文的统计信息（消息数、Token 数等）
  /quit       - 退出程序

提示:
  - 直接输入问题即可与 Kimi 对话
  - 当对话超过 20 轮或 Token 超过 8000 时，建议使用压缩功能
  - 智能压缩会调用 AI API，产生额外费用，但效果更好
""")


def print_tools(soul: KimiSoul):
    """
    打印所有可用工具

    参数:
        soul: KimiSoul 对象，包含工具注册表
    """
    # 获取所有工具
    tools = soul._tools.list_tools()

    print("\n可用工具:")
    print("-" * 50)

    # 遍历并打印每个工具
    for tool in tools:
        print(f"\n  🔧 {tool.name}")
        print(f"     {tool.description}")
    print()


def print_streaming_response(soul: KimiSoul, user_input: str):
    """
    打印流式响应

    什么是流式输出？
    普通输出：等待 AI 生成完整回复，然后一次性显示
    流式输出：AI 生成一个字，就立即显示一个字，像打字一样

    优点：
    1. 用户感知更快（不用等很久）
    2. 体验更自然（像在实时对话）

    参数:
        soul: KimiSoul 对象
        user_input: 用户的输入文本
    """
    # 打印 AI 标签，不换行（end=""）
    # flush=True 确保立即显示，不等待缓冲区满
    print("🤖 Kimi: ", end="", flush=True)

    full_content = ""      # 用于存储完整内容
    step_count = 0         # 记录处理步数
    tool_calls_info = []   # 记录工具调用信息

    # 调用流式对话方法
    # 它返回一个生成器，每次 yield 一个事件
    for event in soul.run_turn_stream(user_input):

        # 事件类型 1：普通内容（AI 生成的文字）
        if event["type"] == "content":
            # 立即打印这个字/词
            print(event["content"], end="", flush=True)
            full_content += event["content"]

        # 事件类型 2：开始思考（thinking 模式）
        elif event["type"] == "reasoning_start":
            print("\n💭 ", end="", flush=True)

        # 事件类型 3：思考内容
        elif event["type"] == "reasoning":
            print(event["content"], end="", flush=True)

        # 事件类型 4：工具调用
        elif event["type"] == "tool_calls":
            tool_calls_info = event["tool_calls"]
            # 显示每个工具的调用详情
            print("\n")
            for tc in tool_calls_info:
                tool_display = tc['name']
                # 如果是 SearchWeb，显示搜索关键词
                if 'SearchWeb' in tool_display:
                    print(f"  [调用工具] {tool_display}")
                else:
                    print(f"  [调用工具] {tool_display}")
                # 显示其他重要参数
                args = tc.get('arguments', {})
                if args and 'SearchWeb' not in tool_display:
                    # 显示前3个参数
                    arg_strs = []
                    for k, v in list(args.items())[:3]:
                        v_str = str(v)
                        if len(v_str) > 30:
                            v_str = v_str[:30] + "..."
                        arg_strs.append(f"{k}={v_str}")
                    if arg_strs:
                        print(f"            参数: {', '.join(arg_strs)}")

        # 事件类型 5：工具执行结果
        elif event["type"] == "tool_result":
            result = event["result"]
            tool_name = event.get("tool_name", "")

            # 判断结果类型并显示不同图标
            if result.startswith("Error"):
                icon = "❌"
                prefix = "失败"
            elif result.startswith("警告"):
                icon = "⚠️"
                prefix = "警告"
            else:
                icon = "✅"
                prefix = "成功"

            # 截断显示
            if len(result) > 200:
                result = result[:200] + "..."
            print(f"  [{icon} {prefix}] {result}")

        # 事件类型 6：整轮对话结束
        elif event["type"] == "turn_done":
            step_count = event.get("step_count", 0)
            if event["success"]:
                # 如果用了多步（有工具调用），显示统计
                if step_count > 1:
                    print(f"\n   (使用了 {step_count} 步)")
            else:
                print(f"\n❌ 错误: {event['message']}")

    # 最后打印换行
    print("\n")


def print_stats(soul: KimiSoul):
    """
    打印上下文统计信息

    帮助用户了解当前对话的状态
    """
    from .compaction import estimate_tokens

    messages = soul._messages

    # 统计各种角色的消息数量
    system_count = sum(1 for m in messages if m.role == "system")
    user_count = sum(1 for m in messages if m.role == "user")
    assistant_count = sum(1 for m in messages if m.role == "assistant")
    tool_count = sum(1 for m in messages if m.role == "tool")

    # 估算 Token 数
    token_count = estimate_tokens(messages)

    print("\n📊 上下文统计:")
    print("-" * 40)
    print(f"  总消息数: {len(messages)}")
    print(f"    - 系统提示: {system_count}")
    print(f"    - 用户消息: {user_count}")
    print(f"    - AI 回复: {assistant_count}")
    print(f"    - 工具结果: {tool_count}")
    print(f"  估算 Token: ~{token_count}")

    # 给出建议
    if token_count > 12000:
        print(f"\n  ⚠️  Token 较多，建议压缩 (/compact 或 /compact-ai)")
    elif token_count > 8000:
        print(f"\n  💡 Token 适中，长对话后建议压缩")
    else:
        print(f"\n  ✅ Token 正常")

    # 显示工具执行统计
    tool_stats = soul.get_tool_stats()
    if tool_stats:
        print("\n  工具执行统计:")
        for tool_name, stats in tool_stats.items():
            calls = stats["calls"]
            success_rate = (stats["successes"] / calls * 100) if calls > 0 else 0
            print(f"    - {tool_name}: {calls} 次调用, {success_rate:.0f}% 成功率")

    print()


def main():
    """
    主函数 - 程序的入口

    执行流程：
    1. 显示欢迎信息
    2. 加载配置
    3. 创建 Runtime、Agent、KimiSoul
    4. 运行主循环，处理用户输入
    """
    # 1. 打印欢迎信息
    print_welcome()

    # 2. 加载配置（从 .env 文件或环境变量）
    try:
        config = load_config_from_env()
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print("\n请设置环境变量:")
        print('  export OPENAI_API_KEY="your-api-key"')
        print('  export OPENAI_BASE_URL="https://api.moonshot.cn/v1"  # 可选')
        sys.exit(1)  # 退出程序，返回错误码 1

    # 3. 尝试加载已存在的会话
    work_dir = Path.cwd()  # 获取当前工作目录
    session_path = work_dir / ".kimi_session.json"

    if session_path.exists():
        print(f"💾 发现已有会话: {session_path}")
        try:
            # 从文件加载会话
            soul = KimiSoul.load_session(session_path, config)
            print(f"✅ 已加载会话，历史消息: {len(soul._messages)} 条")
        except Exception as e:
            print(f"⚠️ 加载会话失败: {e}")
            print("🆕 创建新会话...")
            # 加载失败则创建新会话
            runtime = Runtime.create(config)
            agent = Agent.create(runtime)
            soul = KimiSoul(agent)
    else:
        # 没有会话文件，创建新的
        print("🆕 创建新会话...")
        runtime = Runtime.create(config)
        agent = Agent.create(runtime)
        soul = KimiSoul(agent)

    # 显示状态信息
    print(f"✅ 已连接模型: {config.llm.model}")
    print(f"📁 工作目录: {work_dir}")
    print(f"🔧 可用工具: {len(soul._tools.list_tools())} 个")
    print(f"💡 提示: 输入 /help 查看命令，或直接用自然语言提问\n")

    # 4. 主循环
    while True:
        try:
            # 获取用户输入
            # strip() 去除首尾空白字符
            user_input = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # 处理 Ctrl+C 或 Ctrl+D
            print("\n\n再见！")
            break

        # 如果输入为空，跳过
        if not user_input:
            continue

        # 处理命令（以 / 开头）
        if user_input.startswith("/"):
            # 去除 /，转为小写，分割成命令和参数
            parts = user_input[1:].lower().split()
            cmd = parts[0] if parts else ""

            if cmd in ("quit", "exit", "q"):
                print("\n再见！")
                break

            elif cmd == "help":
                print_help()

            elif cmd == "tools":
                print_tools(soul)

            elif cmd == "clear":
                # 清空历史，但保留系统提示
                soul.clear_history()
                print("✅ 对话历史已清空\n")

            elif cmd == "save":
                try:
                    saved_path = soul.save_session()
                    print(f"✅ 会话已保存: {saved_path}\n")
                except Exception as e:
                    print(f"❌ 保存失败: {e}\n")

            elif cmd == "load":
                try:
                    soul = KimiSoul.load_session(session_path, config)
                    print(f"✅ 会话已加载，历史消息: {len(soul._messages)} 条\n")
                except Exception as e:
                    print(f"❌ 加载失败: {e}\n")

            elif cmd == "stats":
                print_stats(soul)

            elif cmd == "compact":
                # 简单压缩
                from .compaction import compact_messages_simple, estimate_tokens

                original_count = len(soul._messages)
                original_tokens = estimate_tokens(soul._messages)

                if original_count <= 6:
                    print("💡 消息较少，无需压缩\n")
                    continue

                # 执行压缩
                soul._messages = compact_messages_simple(soul._messages)

                # 显示统计
                compressed_tokens = estimate_tokens(soul._messages)
                print(f"✅ 简单压缩完成:")
                print(f"   消息: {original_count} → {len(soul._messages)} 条")
                print(f"   Token: ~{original_tokens} → ~{compressed_tokens}\n")

            elif cmd == "compact-ai":
                # 智能压缩（使用 AI）
                from .compaction import compact_messages_smart, estimate_tokens

                original_count = len(soul._messages)
                original_tokens = estimate_tokens(soul._messages)

                if original_count <= 6:
                    print("💡 消息较少，无需压缩\n")
                    continue

                print("🤖 正在使用 AI 生成智能摘要...")
                print("   （这会消耗一些 Token）\n")

                try:
                    # 执行智能压缩
                    soul._messages = compact_messages_smart(
                        soul._messages,
                        soul._llm,
                        keep_recent=2,  # 保留最近 2 轮
                    )

                    # 显示统计
                    compressed_tokens = estimate_tokens(soul._messages)
                    print(f"✅ 智能压缩完成:")
                    print(f"   消息: {original_count} → {len(soul._messages)} 条")
                    print(f"   Token: ~{original_tokens} → ~{compressed_tokens}")
                    print(f"   节省: ~{original_tokens - compressed_tokens} Token\n")

                except Exception as e:
                    print(f"❌ 压缩失败: {e}\n")

            else:
                print(f"❌ 未知命令: {user_input}")
                print("   输入 /help 查看可用命令\n")

            continue  # 跳过下面的对话处理

        # 5. 处理普通对话（非命令）

        # 检查是否需要提示压缩
        from .compaction import estimate_tokens
        total_chars = sum(len(m.content) for m in soul._messages)
        estimated_tokens = estimate_tokens(soul._messages)

        if total_chars > 20000 or estimated_tokens > 8000:
            print(f"⚠️  提示：上下文较长（~{estimated_tokens} Token）")
            print("    建议使用 /compact 或 /compact-ai 压缩\n")

        # 运行流式对话
        print_streaming_response(soul, user_input)


# 程序入口
if __name__ == "__main__":
    main()

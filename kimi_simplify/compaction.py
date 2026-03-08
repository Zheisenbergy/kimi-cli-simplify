"""
上下文压缩模块

当对话历史太长时，压缩早期消息以节省 Token。

什么是 Token？
- Token 是 AI 模型处理文本的最小单位
- 英文约 4 个字母 = 1 Token
- 中文约 1.5 个汉字 = 1 Token
- 模型有 Token 上限（如 8k、32k、128k）

为什么需要压缩？
1. 防止超过模型的最大上下文限制
2. 节省 API 调用费用（按 Token 计费）
3. 提高响应速度（处理短文本更快）

压缩策略：
1. 简单压缩：按规则提取（代码少、速度快、质量一般）
2. 智能压缩：用 AI 生成摘要（代码多、需要调用 API、质量高）
"""

from __future__ import annotations

# 从 llm 模块导入 Message 类
# Message 是消息对象，包含 role（角色）、content（内容）等信息
from .llm import Message, LLM


def compact_messages_simple(
    messages: list[Message],
    keep_recent: int = 6,
    max_summary_length: int = 500,
) -> list[Message]:
    """
    简单压缩：按规则提取关键信息

    参数说明：
        messages: 原始消息列表，包含所有对话历史
        keep_recent: 保留最近的多少轮对话（一轮 = 用户问 + AI答）
        max_summary_length: 摘要的最大长度（字符数）

    返回值：
        压缩后的消息列表

    压缩策略：
    1. 保留系统消息（System Prompt，告诉 AI 怎么回答）
    2. 保留最近的 N 轮对话（用户和 AI 的完整对话）
    3. 将更早的对话压缩成文本摘要
    """
    # 如果消息不多（少于 keep_recent * 3），不需要压缩
    # 乘以 3 是因为一轮对话通常包含：用户消息 + AI消息 + 可能工具结果
    if len(messages) <= keep_recent * 3:
        return messages  # 直接返回，不压缩

    # 第一步：分离系统消息和普通消息
    # 系统消息是特殊的，它告诉 AI 怎么回答，必须保留
    system_msgs = [m for m in messages if m.role == "system"]

    # 普通消息包括：user（用户）、assistant（AI）、tool（工具结果）
    non_system = [m for m in messages if m.role != "system"]

    # 如果普通消息不多，也不压缩
    if len(non_system) <= keep_recent * 3:
        return messages

    # 第二步：保留最近的消息
    # Python 切片语法：list[-n:] 表示取最后 n 个元素
    # 例如：keep_recent=6，就保留最后 18 条消息（6轮 * 每轮3条）
    recent_messages = non_system[-keep_recent * 3:]

    # 第三步：获取需要压缩的旧消息
    # list[:-n] 表示取除了最后 n 个之外的所有元素
    old_messages = non_system[:-keep_recent * 3]

    # 第四步：生成摘要
    # 调用 _generate_summary_simple 函数，用简单规则提取关键信息
    summary = _generate_summary_simple(old_messages, max_summary_length)

    # 第五步：构建新的消息列表
    result = system_msgs.copy()  # 先复制系统消息

    # 添加摘要作为一条"用户消息"
    # 这样 AI 会把它当作上下文来理解
    result.append(Message(
        role="user",
        content=f"[上下文摘要] 之前的对话内容:\n{summary}\n[摘要结束] 请继续回答。",
    ))

    # 添加 AI 的"确认消息"
    # 这模拟了 AI 理解了摘要的过程，让对话更自然
    result.append(Message(
        role="assistant",
        content="好的，我已了解之前的对话内容，请继续。",
    ))

    # 最后添加保留的近期消息（完整保留，不压缩）
    result.extend(recent_messages)

    return result


def _generate_summary_simple(messages: list[Message], max_length: int) -> str:
    """
    用简单规则生成消息摘要

    参数：
        messages: 需要摘要的消息列表
        max_length: 摘要最大长度

    返回值：
        摘要文本

    规则说明：
    - 提取用户的问题（用户消息）
    - 记录 AI 使用了哪些工具（工具调用）
    - 忽略工具的具体结果（通常很长但不太重要）
    """
    # 用于存储摘要的各个部分
    summary_parts = []

    # 遍历所有消息
    for msg in messages:
        # 如果是用户消息，提取问题
        if msg.role == "user":
            content = msg.content
            # 如果内容太长，只取前 200 个字符
            if len(content) > 200:
                content = content[:200] + "..."
            # 添加到摘要
            summary_parts.append(f"- 用户: {content}")

        # 如果是 AI 消息且有工具调用，记录工具名
        elif msg.role == "assistant" and msg.tool_calls:
            # tool_calls 是列表，可能同时调用多个工具
            for tc in msg.tool_calls:
                summary_parts.append(f"- 使用了 {tc.name} 工具")

    # 用换行符连接所有摘要部分
    summary = "\n".join(summary_parts)

    # 如果摘要太长，截断并添加省略号
    if len(summary) > max_length:
        summary = summary[:max_length] + "\n... (更多内容已省略)"

    # 如果摘要是空的，返回默认文本
    if not summary:
        return "(无重要内容)"

    return summary


def compact_messages_smart(
    messages: list[Message],
    llm: LLM,
    keep_recent: int = 2,
) -> list[Message]:
    """
    智能压缩：用 AI 生成高质量的摘要

    参数说明：
        messages: 原始消息列表
        llm: LLM 对象，用于生成摘要（需要调用 API）
        keep_recent: 保留最近的多少轮对话（建议 2-4 轮）

    返回值：
        压缩后的消息列表

    与简单压缩的区别：
    1. 使用 AI 理解内容，而不是机械规则
    2. 能识别重要信息（如错误、解决方案、关键代码）
    3. 生成结构化的摘要
    4. 需要调用 API，有额外成本

    成本提示：
    - 每次压缩会消耗 Token（输入：长对话，输出：摘要）
    - 建议只在对话超过 20 轮或 Token 超过 8000 时使用
    """
    # 如果消息不多，不需要压缩
    if len(messages) <= keep_recent * 3:
        return messages

    # 第一步：分离系统消息
    system_msgs = [m for m in messages if m.role == "system"]
    non_system = [m for m in messages if m.role != "system"]

    # 第二步：分离保留部分和待压缩部分
    # 从后往前数，保留 keep_recent 轮对话
    recent_messages = non_system[-keep_recent * 3:]
    old_messages = non_system[:-keep_recent * 3]

    # 如果没有旧消息需要压缩，直接返回
    if not old_messages:
        return messages

    # 第三步：构建压缩提示词（Prompt）
    # 这是告诉 AI 怎么压缩的指令
    compaction_prompt = """请压缩以下对话历史。

你需要保留的关键信息（按重要性排序）：
1. **当前任务**：用户正在做什么
2. **错误和解决**：遇到的错误及如何解决
3. **代码状态**：最终的代码（删除中间失败的尝试）
4. **设计决策**：为什么选择某种方案
5. **待办事项**：未完成的任务

请按以下格式输出：

<current_focus>
用户正在做什么任务
</current_focus>

<completed>
- 完成了什么：结果是什么
</completed>

<errors>
- 遇到什么错误：如何解决
</errors>

<files>
文件名: 当前状态（如 "已创建"、"已修改"）
关键代码片段（保留最重要的部分）
</files>

<todos>
- 待办：未完成的事项
</todos>

以下是对话历史：
"""

    # 第四步：将旧消息格式化为文本
    # 我们把每条消息转换成 "角色: 内容" 的格式
    history_text = ""
    for i, msg in enumerate(old_messages, 1):
        history_text += f"\n--- 消息 {i} ({msg.role}) ---\n"
        history_text += msg.content[:1000]  # 限制单条消息长度，避免太长

        # 如果有工具调用，也记录下来
        if msg.tool_calls:
            history_text += "\n[工具调用]:"
            for tc in msg.tool_calls:
                history_text += f"\n- {tc.name}({tc.arguments})"

    # 第五步：调用 LLM 生成摘要
    # 创建压缩用的消息列表
    compaction_messages = [
        # 系统消息：告诉 AI 它的任务
        Message(role="system", content="你是一个专业的对话压缩助手。你的任务是理解对话历史，提取关键信息，生成简洁但完整的摘要。"),
        # 用户消息：包含压缩指令和对话历史
        Message(role="user", content=compaction_prompt + history_text),
    ]

    # 调用 LLM（非流式，因为我们需要完整摘要）
    print("  [压缩] 正在生成智能摘要...", end="", flush=True)
    response = llm.chat(compaction_messages)
    print(" 完成")

    # 第六步：构建压缩后的消息列表
    result = system_msgs.copy()

    # 添加摘要消息
    # 我们用 "system" 角色，因为这更像是一个系统级的上下文信息
    result.append(Message(
        role="system",
        content=f"[上下文摘要] {response.content}\n[摘要结束]",
    ))

    # 添加保留的近期消息
    result.extend(recent_messages)

    return result


def estimate_tokens(messages: list[Message]) -> int:
    """
    估算 Token 数量

    这是一个粗略的估计，用于判断是否需要进行压缩。

    估算规则：
    - 英文约 4 个字符 = 1 Token
    - 中文约 1.5 个字符 = 1 Token
    - 这里使用保守估计：3 字符/Token

    参数：
        messages: 消息列表

    返回值：
        估算的 Token 数量
    """
    # 计算所有消息内容的长度总和
    total_chars = sum(len(m.content) for m in messages)

    # 除以 3 得到 Token 估算值
    # 为什么是 3？因为这是一个保守估计，介于中文和英文之间
    return total_chars // 3


def should_compact(messages: list[Message], max_tokens: int = 8000) -> bool:
    """
    判断是否需要压缩

    参数：
        messages: 消息列表
        max_tokens: 最大 Token 限制（默认 8000）

    返回值：
        True - 需要压缩
        False - 不需要
    """
    estimated = estimate_tokens(messages)
    return estimated > max_tokens


def get_compression_stats(messages: list[Message], compressed: list[Message]) -> dict:
    """
    获取压缩统计信息

    参数：
        messages: 原始消息列表
        compressed: 压缩后的消息列表

    返回值：
        包含统计信息的字典
    """
    original_count = len(messages)
    compressed_count = len(compressed)

    original_tokens = estimate_tokens(messages)
    compressed_tokens = estimate_tokens(compressed)

    return {
        "original_messages": original_count,
        "compressed_messages": compressed_count,
        "message_reduction": original_count - compressed_count,
        "message_reduction_percent": round((1 - compressed_count / original_count) * 100, 1),
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "token_reduction": original_tokens - compressed_tokens,
        "token_reduction_percent": round((1 - compressed_tokens / original_tokens) * 100, 1),
    }

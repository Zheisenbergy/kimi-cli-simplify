"""
LLM（大语言模型）接口封装模块

什么是 LLM？
LLM = Large Language Model（大语言模型）
比如：GPT-4、Claude、Kimi、通义千问等
它们能理解和生成自然语言

为什么需要封装？
直接使用 OpenAI SDK 也可以，但封装后可以：
1. 统一接口：更换模型时不需要改很多代码
2. 类型安全：用 Python 类型注解，减少错误
3. 方便扩展：可以添加流式输出、重试等功能

OpenAI SDK 是什么？
OpenAI 提供的 Python 库，用来调用他们的 API
安装：pip install openai
"""

from __future__ import annotations

# dataclass: 用于创建简单的数据类，自动生成 __init__、__repr__ 等方法
from dataclasses import dataclass, field

# typing: Python 的类型注解模块
# Any 表示任意类型，在不确定类型时使用
from typing import Any

# OpenAI 官方提供的 Python SDK
from openai import OpenAI


@dataclass
class ToolCall:
    """
    工具调用数据类

    什么是工具调用？
    LLM 不仅可以生成文本，还可以"调用工具"来完成任务
    比如：读取文件、执行命令、搜索网页等

    当 LLM 觉得需要工具时，会返回 tool_calls
    程序执行工具后，把结果再发给 LLM
    LLM 根据工具结果生成最终回答

    属性说明：
        id: 工具调用的唯一标识符，用于匹配结果
        name: 工具名称，比如 "ReadFile"
        arguments: 工具参数，比如 {"path": "file.txt"}
    """
    id: str                          # 工具调用的唯一 ID
    name: str                        # 工具名称
    arguments: dict[str, Any]        # 工具参数（字典类型）


@dataclass
class Message:
    """
    消息数据类

    什么是对话消息？
    和 LLM 的对话由一条条消息组成，每条消息有：
    - role（角色）：谁发的消息
    - content（内容）：消息内容
    - 其他可选信息

    role 可以是：
    - "system": 系统提示，告诉 AI 怎么回答
    - "user": 用户发的消息
    - "assistant": AI 助手发的消息
    - "tool": 工具执行的结果

    属性说明：
        role: 消息角色
        content: 消息内容（文本）
        tool_calls: AI 请求调用的工具列表
        tool_call_id: 工具结果的 ID，对应 tool_calls 中的 id
        reasoning_content: 思考内容（如果模型支持 thinking 模式）
    """
    role: str                                    # 消息角色
    content: str = ""                           # 消息内容，默认为空字符串
    tool_calls: list[ToolCall] = field(default_factory=list)  # 工具调用列表
    tool_call_id: str | None = None             # 工具结果对应的工具 ID
    reasoning_content: str | None = None        # 思考过程（有的模型会展示思考过程）


class LLM:
    """
    LLM 封装类

    这个类封装了与 LLM 交互的所有操作
    包括：发送消息、接收响应、流式输出等

    什么是类（Class）？
    类是创建对象的"蓝图"，定义了对象的属性和方法
    比如：class Dog: 定义了狗这个物种，可以创建 dog1、dog2 等具体对象

    什么是对象（Object）？
    对象是类的实例，有具体的数据
    比如：dog1 = Dog(name="小白") 就是一个具体的狗对象
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        """
        构造函数：创建 LLM 对象时调用

        什么是 __init__？
        这是 Python 类的构造函数，创建对象时自动执行
        用来初始化对象的属性

        参数说明：
            api_key: API 密钥，用于身份验证
            base_url: API 服务器地址
            model: 使用的模型名称
        """
        # self 表示当前对象自己
        # 把参数保存为对象的属性，这样其他方法可以用
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: list[Message], tools: list[dict] | None = None) -> Message:
        """
        发送消息并获取响应（非流式）

        什么是非流式？
        一次性发送请求，等待 AI 生成完整回复后返回
        优点是代码简单，缺点是等待时间长（用户看不到过程）

        参数说明：
            messages: 历史消息列表，包含对话上下文
            tools: 可选的工具定义列表，告诉 AI 有哪些工具可用

        返回值：
            Message 对象，包含 AI 的回复
        """
        # 把我们的 Message 对象转换成 OpenAI SDK 需要的格式
        api_messages = []
        for msg in messages:
            # 创建字典类型的消息
            api_msg: dict = {"role": msg.role, "content": msg.content}

            # 如果有 reasoning_content（思考内容），也加上
            if msg.reasoning_content:
                api_msg["reasoning_content"] = msg.reasoning_content

            # 如果有工具调用，转换成 API 格式
            if msg.tool_calls:
                api_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            # arguments 需要是字符串（JSON 格式）
                            "arguments": str(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            # 如果是工具结果，加上 tool_call_id
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id

            api_messages.append(api_msg)

        # 构建请求参数
        kwargs: dict = {
            "model": self.model,
            "messages": api_messages,
        }

        # 如果提供了工具定义，加到请求中
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"  # 让 AI 自己决定要不要用工具

        # 调用 OpenAI API
        # response 是 API 的原始响应对象
        response = self.client.chat.completions.create(**kwargs)

        # 提取响应内容
        choice = response.choices[0]  # 通常只有一个选择
        msg = choice.message          # 获取消息对象

        # 解析 tool_calls（工具调用请求）
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                import json  # json 模块用于解析 JSON 字符串

                # 解析参数（从 JSON 字符串转为 Python 字典）
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)  # JSON 字符串转字典
                    except json.JSONDecodeError:
                        args = {}  # 解析失败就用空字典

                # 创建 ToolCall 对象
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        # 提取 reasoning_content（思考内容）
        # getattr(obj, "attr", default) 安全地获取属性，不存在时返回 default
        reasoning_content = getattr(msg, "reasoning_content", None)

        # 返回 Message 对象
        return Message(
            role="assistant",
            content=msg.content or "",  # 如果 content 是 None，用空字符串
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )

    def chat_stream(self, messages: list[Message], tools: list[dict] | None = None):
        """
        流式发送消息并获取响应

        什么是流式（Stream）？
        普通请求：等 AI 写完所有内容，一次性返回
        流式请求：AI 每写一个字，立即返回一个字
        用户体验更好，像在看实时打字

        参数说明：
            messages: 历史消息列表
            tools: 可选的工具定义列表

        Yields:
            流式事件字典，包含不同类型的数据
            调用者需要用 for 循环接收这些事件

        什么是 yield？
        yield 用于创建生成器（Generator）
        生成器可以暂停执行，返回一个值，下次从暂停处继续
        这样可以实现"边生成边返回"，而不是等全部生成完

        普通函数：
            def normal():
                return [1, 2, 3]  # 等全部准备好，一次性返回

        生成器函数：
            def generator():
                yield 1  # 返回 1，暂停
                yield 2  # 返回 2，暂停
                yield 3  # 返回 3，结束

        使用时：
            for item in generator():
                print(item)  # 会依次打印 1、2、3
        """
        # 转换消息格式（和非流式一样）
        api_messages = []
        for msg in messages:
            api_msg: dict = {"role": msg.role, "content": msg.content}
            if msg.reasoning_content:
                api_msg["reasoning_content"] = msg.reasoning_content
            if msg.tool_calls:
                api_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": str(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id
            api_messages.append(api_msg)

        # 构建请求参数
        kwargs: dict = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,  # 🔴 关键：开启流式模式
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # 发起流式请求
        # stream 是一个迭代器，每次返回一个数据块（chunk）
        stream = self.client.chat.completions.create(**kwargs)

        # 用于累积完整响应的变量
        full_content = ""                    # 累积完整文本
        tool_calls_buffer: dict = {}         # 累积工具调用信息
        reasoning_content: str | None = None  # 累积思考内容

        # 遍历流式响应的每个数据块
        for chunk in stream:
            # chunk 是增量数据，只包含新产生的部分
            delta = chunk.choices[0].delta

            # 情况 1：思考内容（如果模型支持 thinking 模式）
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                # 第一次收到思考内容时
                if reasoning_content is None:
                    reasoning_content = ""
                    yield {"type": "reasoning_start"}  # 通知调用者开始思考

                reasoning_content += delta.reasoning_content
                yield {
                    "type": "reasoning",
                    "content": delta.reasoning_content,
                }

            # 情况 2：普通内容（AI 生成的文本）
            if delta.content:
                full_content += delta.content
                yield {
                    "type": "content",
                    "content": delta.content,  # 只返回新的部分
                }

            # 情况 3：工具调用（流式解析，逐步累积）
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    index = tc.index  # 工具调用的索引（可能同时调用多个工具）

                    # 如果是新的工具调用，初始化缓冲区
                    if index not in tool_calls_buffer:
                        tool_calls_buffer[index] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }

                    # 累积工具调用信息（流式返回的可能是片段）
                    if tc.id:
                        tool_calls_buffer[index]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_buffer[index]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_buffer[index]["arguments"] += tc.function.arguments

        # 流结束后，解析完整的工具调用
        tool_calls = []
        import json
        for index in sorted(tool_calls_buffer.keys()):
            tc_data = tool_calls_buffer[index]
            try:
                args = json.loads(tc_data["arguments"])  # JSON 字符串转字典
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(
                id=tc_data["id"],
                name=tc_data["name"],
                arguments=args,
            ))

        # 返回最终结果
        yield {
            "type": "done",
            "message": Message(
                role="assistant",
                content=full_content,
                tool_calls=tool_calls,
                reasoning_content=reasoning_content,
            ),
        }


# 测试代码
if __name__ == "__main__":
    print("这是 LLM 模块，运行主程序请执行: python -m kimi_simplify.main")

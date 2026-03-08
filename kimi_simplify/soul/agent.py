"""
Agent 和 Runtime

这个文件定义了 Agent 架构中的三个核心类：
1. Session（会话）- 存储对话状态
2. Runtime（运行时）- 组装所有组件
3. Agent（智能体）- 配置和系统提示

什么是 Session（会话）？
会话就是一次完整的对话过程，包含：
- 工作目录（work_dir）：当前操作的文件夹
- 消息历史（messages）：所有对话记录

可以把 Session 理解为"对话的存档文件"，就像游戏的存档一样。
你可以随时保存（save）和加载（load）会话。

什么是 Runtime（运行时）？
运行时是 Agent 的执行环境，它把各个组件组装在一起：
- Config（配置）：API Key、模型名称等
- LLM（大模型）：用于对话的 AI 模型
- Session（会话）：存储对话历史
- ToolRegistry（工具注册表）：所有可用工具

Runtime 就像汽车的引擎舱，把所有零件组装好，让车能跑起来。

什么是 Agent？
Agent 是用户直接交互的对象，包含：
- 名称（name）：比如 "kimi-simplify"
- 运行时（runtime）：执行环境
- 系统提示（system_prompt）：告诉 AI 怎么回答

可以这么理解：
- Runtime 是后台的基础设施
- Agent 是面向用户的产品
- Session 是数据存储
"""

from __future__ import annotations

# dataclass: 简化类的定义，自动生成 __init__、__repr__ 等方法
# field: 用于设置字段的默认值
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config
from ..llm import LLM
from ..tools import ToolRegistry


@dataclass
class Session:
    """
    会话状态类

    什么是会话？
    想象你和 AI 聊天，从开始到结束是一次"会话"。
    会话需要记录：
    1. 在哪里工作（work_dir）- 当前文件夹
    2. 聊了什么（messages）- 对话历史

    为什么需要持久化？
    如果不保存，关闭程序后对话就消失了。
    保存后，下次可以继续之前的对话。

    属性说明：
        work_dir: Path 对象，表示工作目录
                 Path 是 Python 处理路径的类，比字符串更好用
        messages: 列表，存储所有 Message 对象
                 field(default_factory=list) 表示默认创建空列表
    """
    work_dir: Path
    messages: list = field(default_factory=list)  # list[Message]

    @staticmethod
    def create(work_dir: str | None = None) -> Session:
        """
        创建新会话（静态工厂方法）

        什么是静态方法（@staticmethod）？
        普通方法需要创建对象后才能调用：obj.method()
        静态方法可以直接用类调用：Class.method()
        不需要创建对象。

        什么是工厂方法？
        就像工厂生产产品一样，这个方法专门用来创建 Session 对象。
        它可以处理一些初始化逻辑，让创建过程更简单。

        参数：
            work_dir: 工作目录路径，None 表示使用当前目录

        返回值：
            新创建的 Session 对象
        """
        # 如果没有提供工作目录，使用当前工作目录
        if work_dir is None:
            work_dir = str(Path.cwd())

        # Path(work_dir).resolve() 将路径转换为绝对路径
        # 比如 "./folder" 会变成 "/home/user/project/folder"
        return Session(work_dir=Path(work_dir).resolve())

    def save(self, path: Path | None = None) -> None:
        """
        保存会话到文件

        什么是序列化？
        Python 对象在内存中，程序关闭就消失了。
        序列化是把对象转换成可以存储的格式（如 JSON）。
        这样即使程序关闭，数据也能保存到硬盘。

        参数：
            path: 保存路径，None 表示默认路径（工作目录/.kimi_session.json）

        保存格式（JSON）：
        {
            "work_dir": "/path/to/work",
            "messages": [
                {"role": "user", "content": "你好", ...},
                ...
            ]
        }
        """
        # 延迟导入，避免循环依赖
        # 循环依赖：A 导入 B，B 又导入 A，会导致错误
        from ..llm import Message

        # 如果没有指定路径，使用默认路径
        if path is None:
            path = self.work_dir / ".kimi_session.json"

        # 构建要保存的数据字典
        # 把 Message 对象转换成字典格式
        data = {
            "work_dir": str(self.work_dir),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in msg.tool_calls
                    ] if msg.tool_calls else [],
                    "tool_call_id": msg.tool_call_id,
                    "reasoning_content": msg.reasoning_content,
                }
                for msg in self.messages
            ]
        }

        # 写入 JSON 文件
        # 'w' 表示写入模式
        # encoding='utf-8' 确保中文能正确保存
        with open(path, 'w', encoding='utf-8') as f:
            import json
            # json.dump: 把字典写入文件
            # ensure_ascii=False: 中文不转义，直接保存
            # indent=2: 格式化输出，缩进 2 个空格，方便阅读
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: Path) -> Session:
        """
        从文件加载会话

        什么是反序列化？
        序列化的逆过程，把文件中的 JSON 数据还原成 Python 对象。

        参数：
            path: 会话文件的路径

        返回值：
            加载的 Session 对象
        """
        from ..llm import Message, ToolCall
        import json

        # 读取 JSON 文件
        # 'r' 表示读取模式
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)  # 把 JSON 字符串解析成字典

        # 创建 Session 对象
        session = Session(work_dir=Path(data["work_dir"]))

        # 把字典数据还原成 Message 对象
        for msg_data in data["messages"]:
            # 还原 ToolCall 列表
            tool_calls = [
                ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                for tc in msg_data.get("tool_calls", [])
            ]

            # 创建 Message 对象并添加到会话
            session.messages.append(Message(
                role=msg_data["role"],
                content=msg_data["content"],
                tool_calls=tool_calls,
                tool_call_id=msg_data.get("tool_call_id"),
                reasoning_content=msg_data.get("reasoning_content"),
            ))

        return session


@dataclass
class Runtime:
    """
    Agent 运行时环境

    什么是运行时？
    运行时是程序执行时的环境，包含所有需要的组件。
    就像一艘船需要：引擎、燃料、船员、地图，
    Runtime 需要：配置、模型、会话、工具。

    为什么需要 Runtime？
    把相关组件打包在一起，方便传递和使用。
    不需要分别传递 config、llm、session，只需要传一个 runtime。

    属性说明：
        config: Config 对象，配置信息
        llm: LLM 对象，大语言模型接口
        session: Session 对象，会话状态
        tool_registry: ToolRegistry 对象，工具注册表
    """
    config: Config
    llm: LLM
    session: Session
    tool_registry: ToolRegistry

    @staticmethod
    def create(
        config: Config,
        session: Session | None = None,
    ) -> Runtime:
        """
        创建运行时

        这是 Runtime 的工厂方法，负责：
        1. 如果没有提供 session，创建新的
        2. 根据 config 创建 LLM 对象
        3. 创建默认的工具注册表
        4. 组装成 Runtime 对象

        参数：
            config: 配置对象
            session: 会话对象，None 则创建新的

        返回值：
            组装好的 Runtime 对象
        """
        # 如果没有提供会话，创建新的
        if session is None:
            session = Session.create()

        # 根据配置创建 LLM 对象
        # LLM 需要 API Key、服务器地址、模型名称
        llm = LLM(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
        )

        # 导入并创建默认工具注册表
        # 这会把 ReadFile、WriteFile 等工具都注册好
        from ..tools import create_default_registry
        tool_registry = create_default_registry()

        # 组装并返回 Runtime 对象
        return Runtime(
            config=config,
            llm=llm,
            session=session,
            tool_registry=tool_registry,
        )


@dataclass
class Agent:
    """
    Agent（智能体）

    Agent 是用户直接交互的对象。
    如果说 Runtime 是汽车的引擎和底盘，
    那么 Agent 就是车身和内饰，是用户看到和使用的部分。

    Agent 包含：
    - name: 名称，标识这个 Agent
    - runtime: 运行时环境，提供执行能力
    - system_prompt: 系统提示，告诉 AI 怎么回答

    什么是 System Prompt（系统提示）？
    系统提示是发送给 AI 的"指令"，告诉它：
    - 你是谁（你是一个编程助手）
    - 你能做什么（可以读取文件、执行命令）
    - 应该怎么做（先解释再执行）
    - 不能做什么（不要执行危险操作）

    系统提示用户通常看不到，但会影响 AI 的所有回答。
    """
    name: str
    runtime: Runtime
    system_prompt: str = ""  # 默认空字符串

    @staticmethod
    def create(
        runtime: Runtime,
        name: str = "kimi-simplify",
    ) -> Agent:
        """
        创建 Agent

        参数：
            runtime: 运行时环境
            name: Agent 名称

        返回值：
            配置好的 Agent 对象
        """
        # 构建系统提示词
        # 这会列出所有可用工具，告诉 AI 它能做什么
        system_prompt = _build_system_prompt(runtime)

        # 创建并返回 Agent 对象
        return Agent(
            name=name,
            runtime=runtime,
            system_prompt=system_prompt,
        )


def _build_system_prompt(runtime: Runtime) -> str:
    """
    构建系统提示词

    这是一个私有函数（以下划线开头），只在模块内部使用。

    系统提示词的作用：
    1. 告诉 AI 它的身份（Kimi Simplify）
    2. 列出所有可用工具
    3. 给出使用指南

    参数：
        runtime: 运行时对象，用于获取工具列表

    返回值：
        构建好的系统提示词字符串
    """
    # 获取所有可用工具
    tools = runtime.tool_registry.list_tools()

    # 提取工具名称，用逗号连接
    # 比如：ReadFile, WriteFile, Shell, ...
    tool_names = ", ".join([t.name for t in tools])

    # 使用 f-string（格式化字符串）构建提示词
    # {tool_names} 会被替换成实际的工具名列表
    # {runtime.session.work_dir} 会被替换成工作目录
    return f"""You are Kimi Simplify, a helpful coding assistant.

You have access to the following tools: {tool_names}

Guidelines:
1. When reading files, use line_offset and n_lines for large files
2. When editing files, old_str must match exactly and be unique
3. Shell commands can be used for complex operations
4. Always explain your actions before taking them

Working directory: {runtime.session.work_dir}
"""

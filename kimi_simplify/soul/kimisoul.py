"""
KimiSoul - Agent 核心逻辑

什么是 Agent？
Agent（智能体）是一个能自主决策、执行任务的 AI 系统
和普通聊天机器人的区别：
- 机器人：你问一句，它答一句，完了
- Agent：可以主动使用工具、多轮思考、直到完成任务

Agent 的核心循环：
1. 接收用户输入
2. 思考下一步（调用 LLM）
3. 如果需要，使用工具
4. 根据工具结果，继续思考
5. 重复 2-4，直到得出答案
6. 返回最终答案

什么是上下文（Context）？
上下文就是对话的历史记录
AI 需要根据历史来理解当前的问题

什么是错误处理？
Agent 在执行工具时可能遇到各种错误：
- 工具不存在（AI 产生了幻觉）
- 参数错误（缺少必需参数）
- 执行失败（文件不存在、权限不足）
- 超时（操作太久没完成）
好的错误处理能让 Agent 更健壮，知道何时重试、何时放弃。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Config
from ..errors import ToolResult
from ..llm import Message, ToolCall
from ..tools.executor import ToolExecutor
from .agent import Agent, Runtime, Session


@dataclass
class TurnResult:
    """一轮对话的结果"""
    success: bool
    message: str
    step_count: int = 0


class KimiSoul:
    """Kimi Soul - Agent 的核心"""

    def __init__(
        self,
        agent: Agent,
        use_session_messages: bool = True,
        enable_tool_retry: bool = True,
        tool_timeout: float = 60.0,
    ):
        """
        构造函数

        参数：
            agent: Agent 对象
            use_session_messages: 是否使用 session.messages 实现持久化
            enable_tool_retry: 是否启用工具自动重试
            tool_timeout: 工具执行超时时间（秒）
        """
        self._agent = agent
        self._runtime = agent.runtime
        self._config = agent.runtime.config
        self._llm = agent.runtime.llm
        self._tools = agent.runtime.tool_registry

        # 创建工具执行器（带错误处理和重试）
        self._tool_executor = ToolExecutor(
            max_retries=2 if enable_tool_retry else 0,
            timeout=tool_timeout,
            enable_retry=enable_tool_retry,
            on_retry=self._on_tool_retry,
        )

        # 使用 session.messages 实现持久化
        if use_session_messages:
            self._messages: list[Message] = agent.runtime.session.messages
        else:
            self._messages: list[Message] = []

        # 如果是新会话，添加系统提示
        if not self._messages and agent.system_prompt:
            self._messages.append(Message(role="system", content=agent.system_prompt))

    def run_turn(self, user_input: str) -> TurnResult:
        """运行一轮对话（非流式）"""
        # 添加用户消息到历史
        self._messages.append(Message(role="user", content=user_input))

        step_count = 0
        max_steps = self._config.loop_control.max_steps_per_turn

        while step_count < max_steps:
            step_count += 1

            # 调用 LLM
            tools = self._tools.to_openai_format()
            response = self._llm.chat(self._messages, tools=tools)

            # 如果没有工具调用，直接返回
            if not response.tool_calls:
                self._messages.append(response)
                return TurnResult(
                    success=True,
                    message=response.content,
                    step_count=step_count,
                )

            # 有工具调用，需要执行
            self._messages.append(response)

            # 执行所有工具调用
            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                self._messages.append(Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=tool_call.id,
                ))

        # 达到最大步数
        return TurnResult(
            success=False,
            message=f"Reached max steps ({max_steps})",
            step_count=step_count,
        )

    def run_turn_stream(self, user_input: str):
        """运行一轮对话（流式输出）"""
        self._messages.append(Message(role="user", content=user_input))

        step_count = 0
        max_steps = self._config.loop_control.max_steps_per_turn

        while step_count < max_steps:
            step_count += 1

            tools = self._tools.to_openai_format()
            full_response = None

            for event in self._llm.chat_stream(self._messages, tools=tools):
                if event["type"] == "done":
                    full_response = event["message"]
                else:
                    yield event

            if full_response is None:
                yield {"type": "error", "message": "No response from LLM"}
                return

            if not full_response.tool_calls:
                self._messages.append(full_response)
                yield {
                    "type": "turn_done",
                    "success": True,
                    "message": full_response.content,
                    "step_count": step_count,
                }
                return

            self._messages.append(full_response)

            # 构建工具调用信息，包含参数详情
            tool_calls_info = []
            for tc in full_response.tool_calls:
                # 特殊处理 SearchWeb 工具，显示搜索关键词
                if tc.name == "SearchWeb" and "query" in tc.arguments:
                    display_name = f"{tc.name}(query='{tc.arguments['query']}')"
                else:
                    display_name = tc.name
                tool_calls_info.append({"name": display_name, "arguments": tc.arguments})

            yield {
                "type": "tool_calls",
                "tool_calls": tool_calls_info,
            }

            for tool_call in full_response.tool_calls:
                result = self._execute_tool(tool_call)
                yield {
                    "type": "tool_result",
                    "tool_name": tool_call.name,
                    "result": str(result)[:200],
                }
                self._messages.append(Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=tool_call.id,
                ))

        yield {
            "type": "turn_done",
            "success": False,
            "message": f"Reached max steps ({max_steps})",
            "step_count": step_count,
        }

    def _on_tool_retry(self, tool_name: str, error: Exception, attempt: int) -> None:
        """
        工具重试时的回调

        参数：
            tool_name: 正在重试的工具名称
            error: 导致重试的错误
            attempt: 当前重试次数
        """
        # 这里可以输出日志或发送通知
        # 简化版不直接打印，可以通过事件机制通知上层
        pass

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """
        执行工具调用（带错误处理和重试）

        这是工具执行的主要入口，现在使用 ToolExecutor 来处理：
        1. 参数验证
        2. 超时控制
        3. 错误分类
        4. 自动重试

        参数：
            tool_call: 工具调用请求

        返回值：
            执行结果字符串（成功或错误信息）
        """
        # 获取工具对象
        tool = self._tools.get(tool_call.name)

        # 使用执行器执行工具
        result = self._tool_executor.execute(tool, tool_call.arguments)

        # 转换为字符串返回
        return result.to_message_content()

    def get_tool_stats(self) -> dict:
        """
        获取工具执行统计

        返回值：
            各工具的执行统计数据
        """
        return self._tool_executor.get_stats()

    def print_tool_stats(self) -> None:
        """打印工具执行统计"""
        self._tool_executor.print_stats()

    def get_history(self) -> list[Message]:
        """获取对话历史"""
        return self._messages.copy()

    def clear_history(self) -> None:
        """清空对话历史（保留系统提示）"""
        system_msgs = [msg for msg in self._messages if msg.role == "system"]
        self._messages.clear()
        self._messages.extend(system_msgs)

    def save_session(self, path: Path | None = None) -> Path:
        """保存会话到文件"""
        if path is None:
            path = self._runtime.session.work_dir / ".kimi_session.json"
        self._runtime.session.save(path)
        return path

    @staticmethod
    def load_session(path: Path, config: Config | None = None) -> "KimiSoul":
        """从文件加载会话并创建 KimiSoul"""
        from ..config import load_config_from_env

        if config is None:
            config = load_config_from_env()

        session = Session.load(path)
        runtime = Runtime.create(config, session)
        agent = Agent.create(runtime)
        return KimiSoul(agent, use_session_messages=True)

"""
Soul 模块 - Agent 核心逻辑

什么是 Soul（灵魂）？
在 Agent 架构中，Soul 是核心决策逻辑。
如果说 Agent 是身体，Soul 就是大脑。

这个模块包含三个核心组件：
1. KimiSoul - 核心决策逻辑，处理对话循环
2. Agent - 智能体配置，包含系统提示
3. Runtime - 运行时环境，组装所有组件

使用示例：
    from kimi_simplify.soul import KimiSoul, Agent, Runtime

    # 创建运行时
    runtime = Runtime.create(config)

    # 创建 Agent
    agent = Agent.create(runtime)

    # 创建 KimiSoul
    soul = KimiSoul(agent)

    # 运行对话
    result = soul.run_turn("你好")

__all__ 是什么？
__all__ 定义了当使用 "from module import *" 时，
哪些名字会被导入。这是一种控制公开接口的方式。
"""

from .kimisoul import KimiSoul
from .agent import Agent, Runtime

__all__ = ["KimiSoul", "Agent", "Runtime"]

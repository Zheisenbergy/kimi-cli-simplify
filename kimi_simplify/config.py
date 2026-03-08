"""
配置管理模块

什么是配置？
配置就是程序运行时需要的一些参数，比如：
- API Key（密钥）
- 服务器地址
- 模型名称
- 各种开关选项

为什么要单独一个文件管理配置？
1. 集中管理：所有配置在一个地方，方便修改
2. 环境隔离：开发环境、测试环境、生产环境用不同配置
3. 安全：敏感信息（如 API Key）可以放在环境变量，不写在代码里

什么是环境变量？
环境变量是操作系统层面的变量，程序可以读取
比如：export OPENAI_API_KEY="sk-xxx"
这样程序就能通过 os.environ.get("OPENAI_API_KEY") 读取到
"""

from __future__ import annotations

# os 模块是 Python 标准库，用于和操作系统交互
# 这里用来读取环境变量
import os

# dataclass 是 Python 3.7+ 的装饰器
# 用来自动生成 __init__、__repr__ 等方法，简化类的定义
from dataclasses import dataclass

# Path 用于处理文件路径
# 比直接用字符串好，因为可以跨平台（Windows、Mac、Linux 路径格式不同）
from pathlib import Path

# dotenv 是一个第三方库，用于读取 .env 文件
# .env 文件用来存放环境变量，格式：KEY=value
from dotenv import load_dotenv


# 自动加载 .env 文件
# __file__ 是当前文件的路径
# .parent 是上级目录
# 所以 env_path 是项目根目录下的 .env 文件
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    # load_dotenv 会读取 .env 文件，把里面的 KEY=value 加载到环境变量
    load_dotenv(env_path)


@dataclass
class LLMConfig:
    """
    LLM（大语言模型）配置类

    什么是 dataclass？
    普通类需要写很多样板代码：
        class MyClass:
            def __init__(self, a, b):
                self.a = a
                self.b = b
            def __repr__(self):
                return f"MyClass(a={self.a}, b={self.b})"

    用 @dataclass 装饰器后，只需要：
        @dataclass
        class MyClass:
            a: int
            b: int

    Python 会自动生成 __init__、__repr__、__eq__ 等方法

    属性说明：
        api_key: 调用 API 需要的密钥，类似密码
        base_url: API 服务器的地址
        model: 使用的模型名称，比如 "kimi-k2.5"
    """
    api_key: str          # API 密钥，用于身份验证
    base_url: str = "https://api.moonshot.cn/v1"  # 默认用 Moonshot API
    model: str = "kimi-k2.5"  # 默认模型


@dataclass
class LoopControl:
    """
    循环控制配置

    Agent 会循环执行多个步骤，这个类控制循环的行为：
    - max_steps_per_turn: 一轮对话最多多少步（防止无限循环）
    - max_retries_per_step: 每步失败时重试几次

    为什么需要限制？
    防止程序卡住或花太多时间
    """
    max_steps_per_turn: int = 50   # 一轮最多 50 步，超过就停止
    max_retries_per_step: int = 3  # 每步失败最多重试 3 次


@dataclass
class Config:
    """
    主配置类

    包含所有配置项，是程序的"配置总入口"

    属性：
        llm: LLM 相关的配置（API Key、模型等）
        loop_control: 循环控制配置
        yolo: 是否开启"自动确认"模式（危险操作不询问）
    """
    llm: LLMConfig          # LLM 配置
    loop_control: LoopControl = None  # 循环控制，默认 None
    yolo: bool = False      # YOLO = You Only Live Once，自动确认所有操作

    def __post_init__(self):
        """
        dataclass 初始化后的钩子函数

        如果 loop_control 是 None，自动创建一个默认的
        这样用户就不需要手动创建 LoopControl 对象
        """
        if self.loop_control is None:
            self.loop_control = LoopControl()


def load_config_from_env() -> Config:
    """
    从环境变量加载配置

    什么是函数（Function）？
    函数是一段可重用的代码，输入参数，返回结果
    比如：add(a, b) 函数接收两个数，返回它们的和

    这个函数的作用：
    1. 从环境变量读取 API Key
    2. 创建 Config 对象
    3. 返回配置

    Returns:
        Config 对象，包含所有配置

    Raises:
        ValueError: 如果找不到 OPENAI_API_KEY 环境变量
    """
    # os.environ.get("KEY") 读取环境变量
    # 如果环境变量不存在，返回 None
    api_key = os.environ.get("OPENAI_API_KEY")

    # 如果没有设置 API Key，报错
    # API Key 是必需的，没有它无法调用 AI 接口
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set\n"
            "请先设置环境变量: export OPENAI_API_KEY='your-api-key'"
        )

    # 创建并返回 Config 对象
    return Config(
        llm=LLMConfig(
            api_key=api_key,
            # 读取其他环境变量，如果不存在就用默认值
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.moonshot.cn/v1"),
            model=os.environ.get("KIMI_MODEL", "kimi-k2.5"),
        ),
        # 读取 YOLO 模式，如果环境变量是 "true" 就开启
        yolo=os.environ.get("KIMI_YOLO", "false").lower() == "true",
    )


# 如果这个文件直接运行（不是被导入），执行测试代码
if __name__ == "__main__":
    # 测试配置加载
    try:
        config = load_config_from_env()
        print(f"✅ 配置加载成功")
        print(f"   模型: {config.llm.model}")
        print(f"   API地址: {config.llm.base_url}")
        print(f"   API Key: {config.llm.api_key[:10]}...")
    except ValueError as e:
        print(f"❌ {e}")

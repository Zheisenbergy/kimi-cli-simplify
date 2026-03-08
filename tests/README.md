# 测试说明

## 测试文件

| 文件 | 说明 | 需要 API Key |
|-----|------|------------|
| `test_tools.py` | 测试 6 个内置工具 | ❌ 不需要 |
| `test_soul.py` | 测试 Agent/Runtime/Soul | ❌ 不需要 |
| `test_llm.py` | 测试 LLM 调用 | ✅ 需要 |
| `test_integration.py` | 完整流程测试 | ✅ 需要 |

## 运行测试

### 方法 1: 运行全部测试

```bash
cd /Users/zheisenbergy/code/agent/kimi-cli-simplify

# 不需要 API Key 的测试
python tests/test_tools.py
python tests/test_soul.py

# 需要 API Key 的测试
export OPENAI_API_KEY="your-key"
python tests/test_llm.py
python tests/test_integration.py
```

### 方法 2: 使用测试运行器

```bash
cd /Users/zheisenbergy/code/agent/kimi-cli-simplify

# 运行所有测试（会自动检测 API Key）
python tests/run_tests.py
```

### 方法 3: 使用 pytest（如果安装了）

```bash
cd /Users/zheisenbergy/code/agent/kimi-cli-simplify

# 安装 pytest
pip install pytest

# 运行所有测试
pytest tests/ -v

# 只运行不需要 API Key 的测试
pytest tests/test_tools.py tests/test_soul.py -v
```

## 预期输出

### 工具测试

```
运行工具测试...

✅ test_read_file 通过
✅ test_read_file with offset 通过
✅ test_write_file 通过
✅ test_str_replace 通过
✅ test_shell 通过
✅ test_glob 通过
✅ test_grep 通过

✅ 所有工具测试通过!
```

### Soul 测试

```
运行 Soul 测试...

✅ test_runtime_creation 通过
✅ test_agent_creation 通过
✅ test_soul_creation 通过
✅ test_soul_history 通过

✅ 所有 Soul 测试通过!
```

### LLM 测试

```
运行 LLM 测试...

✅ LLM 响应: 你好！我是 Kimi，一个由月之暗面（Moonshot AI）开发的人工智能助手...
✅ LLM 测试完成!
```

### 集成测试

```
创建 Runtime...
创建 Agent...
创建 Soul...

开始对话测试:

测试 1: 简单对话
----------------------------------------
✅ 成功 (1 步)
回复: 你好！我是 Kimi...

测试 2: 工具调用（列出当前目录）
----------------------------------------
✅ 成功 (2 步)
   (使用了工具)

✅ 集成测试完成!
```

## 手动测试主程序

```bash
# 配置 API Key
export OPENAI_API_KEY="your-key"

# 运行主程序
python -m kimi_simplify.main

# 或使用 uv
uv run python -m kimi_simplify.main
```

然后可以尝试：
- `你好` - 简单对话
- `/tools` - 显示工具
- `/help` - 显示帮助
- `请列出当前目录的文件` - 测试工具调用
- `/quit` - 退出

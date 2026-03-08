"""工具测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kimi_simplify.tools.builtins import _read_file, _write_file, _str_replace, _shell, _glob, _grep


def test_read_file():
    """测试读取文件"""
    # 先创建一个测试文件
    test_path = "/tmp/test_kimi_read.txt"
    with open(test_path, "w") as f:
        f.write("Line 1\nLine 2\nLine 3\n")

    # 测试读取
    result = _read_file(test_path)
    assert "error" not in result, f"读取失败: {result.get('error')}"
    assert "Line 1" in result["output"]
    print("✅ test_read_file 通过")

    # 测试带行号读取
    result = _read_file(test_path, line_offset=2, n_lines=1)
    assert "2" in result["output"]
    assert "Line 2" in result["output"]
    print("✅ test_read_file with offset 通过")

    # 清理
    os.remove(test_path)


def test_write_file():
    """测试写入文件"""
    test_path = "/tmp/test_kimi_write.txt"

    # 测试写入
    result = _write_file(test_path, "Hello World")
    assert "error" not in result, f"写入失败: {result.get('error')}"
    print("✅ test_write_file 通过")

    # 验证内容
    with open(test_path, "r") as f:
        content = f.read()
    assert content == "Hello World"

    # 清理
    os.remove(test_path)


def test_str_replace():
    """测试文本替换"""
    test_path = "/tmp/test_kimi_replace.txt"

    # 先创建文件
    with open(test_path, "w") as f:
        f.write("Hello Old World")

    # 测试替换
    result = _str_replace(test_path, "Old", "New")
    assert "error" not in result, f"替换失败: {result.get('error')}"
    print("✅ test_str_replace 通过")

    # 验证内容
    with open(test_path, "r") as f:
        content = f.read()
    assert content == "Hello New World"

    # 清理
    os.remove(test_path)


def test_shell():
    """测试 shell 命令"""
    result = _shell("echo 'Hello from shell'")
    assert "error" not in result, f"执行失败: {result.get('error')}"
    assert "Hello from shell" in result["output"]
    assert result["exit_code"] == 0
    print("✅ test_shell 通过")


def test_glob():
    """测试文件查找"""
    # 查找 Python 文件
    result = _glob("*.py", path=".")
    assert "error" not in result
    assert "test_tools.py" in result["output"]
    print("✅ test_glob 通过")


def test_grep():
    """测试内容搜索"""
    result = _grep("def test_", path=".")
    assert "error" not in result
    assert "test_tools.py" in result["output"]
    print("✅ test_grep 通过")


if __name__ == "__main__":
    print("运行工具测试...\n")
    test_read_file()
    test_write_file()
    test_str_replace()
    test_shell()
    test_glob()
    test_grep()
    print("\n✅ 所有工具测试通过!")

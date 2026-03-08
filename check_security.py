#!/usr/bin/env python3
"""
安全检测脚本

检查项目中是否存在可能泄露的敏感信息
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def check_git_history():
    """检查 Git 历史中是否包含 .env 文件"""
    print("🔍 检查 Git 历史...")

    try:
        result = subprocess.run(
            ["git", "log", "--all", "--full-history", "--source", "--name-only", "--", ".env"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            print("  ❌ 警告: .env 文件存在于 Git 历史中！")
            print("     请立即执行清理: python check_security.py --clean")
            return False
        else:
            print("  ✅ .env 文件未在 Git 历史中发现")
            return True
    except subprocess.CalledProcessError:
        print("  ⚠️  无法检查 Git 历史（可能不是 Git 仓库）")
        return True


def check_current_env():
    """检查当前工作目录是否有 .env 文件"""
    print("\n🔍 检查当前目录...")

    env_files = list(Path(".").glob("*.env*"))
    env_files = [f for f in env_files if f.name != ".env.example"]

    if env_files:
        print(f"  ⚠️  发现以下环境文件（不应上传到 Git）:")
        for f in env_files:
            print(f"     - {f.name}")
        return False
    else:
        print("  ✅ 未发现 .env 文件（除了 .env.example）")
        return True


def check_gitignore():
    """检查 .gitignore 是否正确配置"""
    print("\n🔍 检查 .gitignore...")

    gitignore = Path(".gitignore")
    if not gitignore.exists():
        print("  ❌ 警告: 未找到 .gitignore 文件！")
        return False

    content = gitignore.read_text()
    if ".env" in content:
        print("  ✅ .env 已在 .gitignore 中")
        return True
    else:
        print("  ❌ 警告: .gitignore 中缺少 .env！")
        return False


def check_api_key_in_code():
    """检查代码中是否硬编码了 API Key"""
    print("\n🔍 检查代码中是否硬编码 API Key...")

    # 只检查真实的 API Key 格式（sk- 开头，48位）
    patterns = [
        r'sk-[a-zA-Z0-9]{48}',  # Moonshot/OpenAI 标准格式
    ]

    # 排除的文件/目录
    exclude_dirs = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.tox'}
    exclude_files = {'check_security.py', '.env.example'}

    found = False
    for root, dirs, files in os.walk("."):
        # 跳过排除的目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file in exclude_files:
                continue

            if file.endswith(('.py', '.md', '.txt', '.yaml', '.yml', '.json', '.sh')):
                filepath = Path(root) / file
                try:
                    content = filepath.read_text(encoding='utf-8')
                    for pattern in patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            # 排除常见的占位符
                            if any(x in match.lower() for x in ['your', 'example', 'test', 'fake', 'placeholder']):
                                continue
                            print(f"  ❌ 发现真实 API Key: {filepath}")
                            print(f"     Key: {match[:20]}...")
                            found = True
                except Exception:
                    continue

    if not found:
        print("  ✅ 未发现硬编码的真实 API Key")
        print("     (配置文件中的变量名是正常的，不属于泄露)")

    return not found


def clean_git_history():
    """清理 Git 历史中的 .env 文件"""
    print("🧹 清理 Git 历史...")

    confirm = input("这将重写 Git 历史，是否继续？ [y/N]: ")
    if confirm.lower() != 'y':
        print("已取消")
        return

    try:
        subprocess.run([
            "git", "filter-branch", "--force", "--index-filter",
            "git rm --cached --ignore-unmatch .env",
            "--prune-empty", "--tag-name-filter", "cat", "--", "--all"
        ], check=True)

        print("\n✅ 历史已清理")
        print("\n下一步:")
        print("  1. 检查确认: git log --all --full-history -- .env")
        print("  2. 强制推送: git push origin main --force")
        print("  3. 通知协作者重新克隆仓库")

    except subprocess.CalledProcessError as e:
        print(f"❌ 清理失败: {e}")


def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "--clean":
        clean_git_history()
        return

    print("=" * 60)
    print("🔒 安全检测工具")
    print("=" * 60)

    checks = [
        ("Git 历史", check_git_history()),
        ("当前目录", check_current_env()),
        (".gitignore", check_gitignore()),
        ("代码扫描", check_api_key_in_code()),
    ]

    print("\n" + "=" * 60)
    print("📋 检测结果")
    print("=" * 60)

    all_passed = True
    for name, passed in checks:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 所有检查通过！")
    else:
        print("\n⚠️  发现安全问题，请根据提示修复")
        print("\n如果 .env 已上传到 Git:")
        print("  1. 立即在 https://platform.moonshot.cn/ 撤销旧 API Key")
        print("  2. 生成新 Key 并更新 .env")
        print("  3. 运行: python check_security.py --clean")


if __name__ == "__main__":
    main()

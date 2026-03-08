"""
内置工具

什么是工具（Tool）？
工具是 Agent 用来与外部世界交互的方式。
LLM 只能生成文本，不能直接操作计算机。
通过工具，LLM 可以：
- 读取你的代码文件
- 修改你的代码
- 执行命令
- 搜索网页

本文件实现了 8 个内置工具：
1. ReadFile     - 读取文件内容
2. WriteFile    - 写入文件
3. StrReplaceFile - 替换文件中的文本
4. Shell        - 执行 shell 命令
5. Glob         - 查找文件（按模式匹配）
6. Grep         - 搜索文件内容
7. SearchWeb    - 网页搜索（DuckDuckGo）
8. FetchURL     - 抓取网页内容

每个工具都是一个函数，遵循相同的模式：
1. 接收参数（如 path, content）
2. 执行操作（如读取、写入）
3. 返回字典，包含：
   - output: 主要输出内容
   - message: 状态信息
   - error: 错误信息（如果有）

为什么返回字典而不是直接返回字符串？
因为字典可以携带更多信息（状态码、元数据等），
方便调用者判断操作是否成功。
"""

from __future__ import annotations

# subprocess: Python 标准库，用于执行系统命令
# 比如运行 "ls", "cat", "git status" 等
import subprocess
from pathlib import Path
from urllib.parse import quote_plus

# 从当前包的 __init__.py 导入 Tool 和 ToolRegistry
from . import Tool, ToolRegistry


def _search_web(query: str, max_results: int = 5) -> dict:
    """
    搜索网页（使用 Bing 国内版）

    为什么选择 Bing？
    Bing 在国内访问稳定，且有国内版（cn.bing.com），
    不需要翻墙即可使用。

    实现原理：
    1. 构造搜索 URL（如 https://cn.bing.com/search?q=python）
    2. 发送 HTTP GET 请求
    3. 解析返回的 HTML，提取搜索结果
    4. 返回标题和链接列表

    参数：
        query: 搜索关键词
        max_results: 最多返回多少条结果（默认 5）

    返回值：
        成功: {"output": "1. 标题\n链接\n\n2. ...", "message": "Found N results"}
        失败: {"output": "", "message": "No results found"} 或 {"error": "..."}
    """
    import socket

    # 设置全局超时（以防万一）
    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(15)

    try:
        # urllib.request: Python 标准库，用于发送 HTTP 请求
        import urllib.request
        import json

        # 使用 Bing 国内版
        # setmkt=zh-CN: 设置市场为中国
        # setlang=zh-CN: 设置语言为中文
        url = f"https://cn.bing.com/search?q={quote_plus(query)}&setmkt=zh-CN&setlang=zh-CN"

        # 设置请求头（模拟浏览器）
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://cn.bing.com/",
        }

        # 创建请求对象
        req = urllib.request.Request(url, headers=headers)

        # 发送请求并获取响应
        # timeout=15: 最多等待 15 秒
        with urllib.request.urlopen(req, timeout=15) as response:
            # 读取响应内容并解码为字符串
            # decode('utf-8'): 把字节转换成字符串
            html = response.read().decode('utf-8')

        # 正则表达式（regex）用于从 HTML 中提取信息
        import re

        results = []

        # Bing 搜索结果解析 - 支持多种可能的 HTML 结构
        # 尝试多种可能的 CSS 类名模式
        patterns = [
            # 新版 Bing 结果
            r'<li class="b_algo"[^>]*>.*?<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?</h2>',
            # 备选模式 1
            r'<div class="b_title"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            # 备选模式 2
            r'<a[^>]*href="([^"]*)"[^>]*target="_blank"[^>]*>(.*?)</a>',
        ]

        matches = []
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            if matches:
                break

        # 处理前 max_results 个结果
        seen_links = set()  # 去重
        for link, title in matches:
            # 跳过广告和无关链接
            if any(skip in link for skip in ['/aclick?', '/adclk?', 'microsoft.com', 'bing.com']):
                continue
            if link in seen_links:
                continue
            seen_links.add(link)

            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', title)
            title = title.strip()

            # 跳过没有标题的结果
            if not title or len(title) < 3:
                continue

            results.append(f"{len(results) + 1}. {title}\n   {link}")

            if len(results) >= max_results:
                break

        if not results:
            return {"output": "", "message": "No results found"}

        output = "\n\n".join(results)
        return {
            "output": output,
            "message": f"Found {len(results)} results",
        }

    except urllib.error.URLError as e:
        # 网络错误（超时、连接失败等）
        return {"error": f"网络错误，无法连接到搜索引擎。可能是网络限制或超时。错误: {e}"}
    except socket.timeout:
        return {"error": "搜索超时。请检查网络连接。"}
    except Exception as e:
        return {"error": f"Search failed: {e}"}
    finally:
        # 恢复原来的超时设置
        socket.setdefaulttimeout(original_timeout)


def _fetch_url(url: str) -> dict:
    """
    抓取网页内容

    什么是网页抓取（Web Scraping）？
    从网页中提取有用的文本信息，去除 HTML 标签、脚本等。
    就像从一堆格式化的文档中提取纯文字内容。

    实现步骤：
    1. 使用完整的浏览器请求头下载网页 HTML
    2. 移除 script 和 style 标签（不需要的代码和样式）
    3. 提取 title 和 body 内容
    4. 移除所有 HTML 标签
    5. 规范化空白字符
    6. 截取前 5000 字符（防止太长）

    关于 403 Forbidden 错误：
    某些网站有反爬虫机制，即使我们模拟浏览器请求头也可能被拒绝。
    常见原因：
    - 网站需要登录/Cookie
    - 网站检测 IP 或请求频率
    - 网站使用 JavaScript 渲染内容
    - 网站限制特定地区访问

    参数：
        url: 要抓取的网页地址

    返回值：
        成功: {"output": "Title: ...\n\nContent:\n...", "message": "Fetched ..."}
        失败: {"error": "..."}
    """
    try:
        import urllib.request
        from html.parser import HTMLParser

        # 设置更完整的请求头，模拟真实浏览器
        # 403 Forbidden 通常是因为请求头不够完整，被识别为爬虫
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

        # 创建请求对象
        req = urllib.request.Request(url, headers=headers)

        # 发送请求，设置 15 秒超时
        # 注意：某些网站可能需要处理重定向和 cookies
        with urllib.request.urlopen(req, timeout=15) as response:
            # errors='ignore': 忽略解码错误（有些网页编码不规范）
            html = response.read().decode('utf-8', errors='ignore')

        import re

        # 第 1 步：移除 script 标签及其内容
        # <script[^>]*> 匹配 <script ...>
        # .*? 匹配内容（非贪婪）
        # </script> 匹配结束标签
        # re.DOTALL | re.IGNORECASE: 忽略大小写，. 匹配换行
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # 第 2 步：移除 style 标签
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # 第 3 步：提取 title
        # re.search: 搜索匹配，返回第一个匹配
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "No title"

        # 第 4 步：提取 body 内容
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
        if body_match:
            content = body_match.group(1)
        else:
            content = html  # 如果没有 body 标签，使用整个 HTML

        # 第 5 步：移除所有 HTML 标签
        # <[^>]+>: 匹配 <...> 格式的所有标签
        content = re.sub(r'<[^>]+>', ' ', content)

        # 第 6 步：规范化空白
        # \s+: 匹配一个或多个空白字符（空格、\t、\n 等）
        content = re.sub(r'\s+', ' ', content)

        # 第 7 步：截取前 5000 字符
        max_len = 5000
        if len(content) > max_len:
            content = content[:max_len] + "..."

        # 组装输出
        output = f"Title: {title}\n\nContent:\n{content.strip()}"

        return {
            "output": output,
            "message": f"Fetched {len(output)} characters from {url}",
        }
    except urllib.error.HTTPError as e:
        # HTTP 错误（如 403 Forbidden, 404 Not Found）
        if e.code == 403:
            return {"error": f"HTTP 403 Forbidden: 该网站拒绝访问。可能原因：\n1. 网站需要登录才能访问\n2. 网站有反爬虫机制\n3. 网站只允许特定地区访问\n建议：尝试使用 SearchWeb 搜索该网站的缓存版本，或直接访问其他来源。"}
        elif e.code == 404:
            return {"error": f"HTTP 404 Not Found: 页面不存在。请检查 URL 是否正确。"}
        elif e.code == 500:
            return {"error": f"HTTP 500 Internal Server Error: 服务器内部错误。"}
        else:
            return {"error": f"HTTP Error {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        # URL 错误（如 DNS 解析失败、连接超时等）
        return {"error": f"URL Error: {e.reason}. 请检查网络连接或 URL 是否正确。"}
    except Exception as e:
        return {"error": f"Failed to fetch URL: {e}"}


def _read_file(path: str, line_offset: int = 1, n_lines: int = 1000) -> dict:
    """
    读取文件内容

    为什么要支持部分读取？
    有些文件可能很大（几千行），全部读取会：
    1. 消耗大量 Token（AI 按 Token 收费）
    2. 超过模型的上下文限制
    3. 处理速度慢

    通过 line_offset 和 n_lines，可以只读取需要的部分。

    参数：
        path: 文件路径
        line_offset: 从第几行开始读取（从 1 开始计数）
        n_lines: 最多读取多少行

    返回值：
        成功: {"output": "带行号的文件内容", "message": "X lines read..."}
        失败: {"error": "File not found: ..."}

    示例：
        _read_file("test.py", line_offset=10, n_lines=5)
        # 返回第 10-14 行的内容
    """
    try:
        # Path(path): 把字符串转换成 Path 对象
        # Path 对象提供了方便的文件操作方法
        p = Path(path)

        # 检查文件是否存在
        if not p.exists():
            return {"error": f"File not found: {path}"}

        # 检查是否是文件（不是目录）
        if not p.is_file():
            return {"error": f"Not a file: {path}"}

        # 打开文件读取
        # 'r': 读取模式（read）
        # encoding='utf-8': 使用 UTF-8 编码（支持中文）
        # errors='replace': 如果解码失败，用 � 替换
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            # readlines(): 读取所有行，返回列表
            # 每个元素是一行文本（包含换行符）
            lines = f.readlines()

        # 计算实际的起始和结束行
        # line_offset - 1: 因为行号从 1 开始，列表索引从 0 开始
        start = max(0, line_offset - 1)
        end = min(start + n_lines, len(lines))

        # 截取需要的行
        selected = lines[start:end]

        # 添加行号并组装结果
        # enumerate(selected, start=start + 1): 从 start+1 开始计数
        # {:6d}: 数字占 6 个字符宽度，右对齐
        # \t: Tab 制表符
        result = ""
        for i, line in enumerate(selected, start=start + 1):
            result += f"{i:6d}\t{line}"

        # 构建消息
        msg = f"{len(selected)} lines read from file starting from line {line_offset}."
        if end < len(lines):
            # 如果还有未读取的内容，提示用户
            msg += f" ({len(lines) - end} more lines available)"

        return {
            "output": result,
            "message": msg,
        }
    except Exception as e:
        return {"error": str(e)}


def _write_file(path: str, content: str) -> dict:
    """
    写入文件

    功能：
    1. 创建新文件（如果文件不存在）
    2. 覆盖旧文件（如果文件已存在）
    3. 自动创建父目录（如果不存在）

    警告：
    这会覆盖原有文件内容，请谨慎使用！

    参数：
        path: 文件路径
        content: 要写入的内容

    返回值：
        成功: {"output": "File written...", "message": "Wrote X characters..."}
        失败: {"error": "..."}
    """
    try:
        p = Path(path)

        # 自动创建父目录
        # parents=True: 创建所有必要的父目录
        # exist_ok=True: 如果目录已存在，不报错
        p.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        # 'w': 写入模式（write），会覆盖原有内容
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)

        return {
            "output": f"File written successfully: {path}",
            "message": f"Wrote {len(content)} characters to {path}",
        }
    except Exception as e:
        return {"error": str(e)}


def _str_replace(path: str, old_str: str, new_str: str) -> dict:
    """
    替换文件中的文本

    使用场景：
    修改代码时，用新代码替换旧代码。
    比如把 print("hello") 改成 print("world")

    为什么要求 old_str 必须唯一？
    如果文件中有多个相同的 old_str，我们不知道替换哪一个。
    要求唯一可以避免误替换。

    参数：
        path: 文件路径
        old_str: 要被替换的文本（必须完全匹配）
        new_str: 新的文本

    返回值：
        成功: {"output": "File edited...", "message": "Text replaced..."}
        失败: {"error": "Could not find the text..."} 或 {"error": "Found multiple occurrences..."}

    示例：
        _str_replace("test.py", 'print("hello")', 'print("world")')
    """
    try:
        p = Path(path)

        if not p.exists():
            return {"error": f"File not found: {path}"}

        # 读取文件内容
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查 old_str 是否存在
        if old_str not in content:
            return {"error": f"Could not find the text in {path}"}

        # 检查 old_str 是否唯一
        if content.count(old_str) > 1:
            return {"error": f"Found multiple occurrences in {path}, please be more specific"}

        # 替换文本（只替换一次）
        new_content = content.replace(old_str, new_str, 1)

        # 写回文件
        with open(p, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return {
            "output": f"File edited successfully: {path}",
            "message": "Text replaced successfully",
        }
    except Exception as e:
        return {"error": str(e)}


def _shell(command: str, timeout: int = 60) -> dict:
    """
    执行 shell 命令

    什么是 Shell？
    Shell 是操作系统的命令行界面。
    在 Linux/macOS 上是 bash/zsh，在 Windows 上是 cmd/PowerShell。

    通过 Shell，可以：
    - 列出文件（ls/dir）
    - 查看文件内容（cat/type）
    - 运行程序（python, npm, git）
    - 等等

    警告：
    执行命令有风险！不要执行不信任的命令。
    比如 "rm -rf /" 会删除整个系统！

    参数：
        command: 要执行的命令字符串
        timeout: 超时时间（秒），默认 60 秒

    返回值：
        成功: {"output": "命令输出", "exit_code": 0, "message": "..."}
        失败: {"output": "错误输出", "exit_code": 1, "message": "..."}
        超时: {"error": "Command timed out..."}
    """
    try:
        # subprocess.run: 执行系统命令
        # shell=True: 通过 shell 执行命令（可以使用管道、重定向等）
        # capture_output=True: 捕获标准输出和标准错误
        # text=True: 以文本模式返回结果（不是字节）
        # timeout: 超时时间
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # 合并 stdout 和 stderr
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr

        # 如果输出太长，截断显示
        max_len = 30000
        if len(output) > max_len:
            output = output[:max_len] + f"\n... [Output truncated, total {len(output)} chars]"

        return {
            "output": output,
            "exit_code": result.returncode,  # 0 表示成功，非 0 表示失败
            "message": f"Command executed with exit code {result.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


def _glob(pattern: str, path: str = ".") -> dict:
    """
    查找文件（按模式匹配）

    什么是 Glob 模式？
    Glob 是一种简单的文件匹配模式，常用通配符：
    - *: 匹配任意字符（不包括 /）
    - **: 匹配任意字符（包括 /），用于递归匹配
    - ?: 匹配单个字符
    - [abc]: 匹配括号内的任意一个字符

    示例：
    - "*.py": 所有 .py 文件
    - "**/*.txt": 所有子目录中的 .txt 文件
    - "src/*.{js,ts}": src 目录下的所有 .js 和 .ts 文件

    参数：
        pattern: 匹配模式
        path: 搜索的起始目录，默认当前目录

    返回值：
        成功: {"output": "file1\nfile2\n...", "message": "Found N files"}
        失败: {"error": "Path not found: ..."}
    """
    try:
        p = Path(path)

        if not p.exists():
            return {"error": f"Path not found: {path}"}

        # rglob: 递归 glob，搜索所有子目录
        # 返回 Path 对象列表
        files = list(p.rglob(pattern))

        # 只保留文件（排除目录）
        # str(f.relative_to(p)): 获取相对于起始目录的路径
        results = [str(f.relative_to(p)) for f in files if f.is_file()]

        if not results:
            return {"output": "", "message": "No files found"}

        # 限制最多返回 1000 个结果
        output = "\n".join(results[:1000])
        msg = f"Found {len(results)} files"
        if len(results) > 1000:
            msg += " (showing first 1000)"

        return {"output": output, "message": msg}
    except Exception as e:
        return {"error": str(e)}


def _grep(pattern: str, path: str = ".") -> dict:
    """
    搜索文件内容

    什么是 Grep？
    Grep 是 "Global Regular Expression Print" 的缩写，
    用于在文件中搜索匹配的文本。
    这是从 Unix/Linux 世界继承来的强大工具。

    实现原理：
    1. 遍历指定路径下的所有文件
    2. 逐行读取每个文件
    3. 检查每行是否包含搜索模式
    4. 收集匹配的行，显示文件名和行号

    参数：
        pattern: 搜索模式（普通字符串）
        path: 搜索的文件或目录，默认当前目录

    返回值：
        成功: {"output": "file:line: content\n...", "message": "Found N matches"}
        失败: {"output": "", "message": "No matches found"}

    示例：
        _grep("def main", "./src")
        # 返回所有包含 "def main" 的行
    """
    try:
        p = Path(path)
        results = []
        count = 0
        max_results = 100  # 最多返回 100 条结果

        # 确定要搜索的文件列表
        if p.is_file():
            # 如果是文件，只搜索这个文件
            files = [p]
        else:
            # 如果是目录，递归搜索所有文件
            files = [f for f in p.rglob("*") if f.is_file()]

        # 遍历文件
        for f in files:
            if count >= max_results:
                break  # 达到上限，停止搜索

            try:
                # 逐行读取文件
                with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                    for i, line in enumerate(file, 1):
                        # enumerate(file, 1): 从 1 开始计数
                        if pattern in line:
                            # 计算相对路径
                            if p in f.parents:
                                rel_path = f.relative_to(p)
                            else:
                                rel_path = f.name

                            # 格式化：文件名:行号: 内容
                            results.append(f"{rel_path}:{i}: {line.rstrip()}")
                            count += 1

                            if count >= max_results:
                                break
            except:
                # 忽略无法读取的文件（如二进制文件）
                continue

        if not results:
            return {"output": "", "message": "No matches found"}

        output = "\n".join(results)
        msg = f"Found {count} matches"
        return {"output": output, "message": msg}
    except Exception as e:
        return {"error": str(e)}


def create_registry() -> ToolRegistry:
    """
    创建默认工具注册表

    这个函数创建并配置 ToolRegistry，注册所有内置工具。
    每个工具都需要定义：
    1. name: 工具名称（英文，大驼峰）
    2. description: 工具描述（告诉 AI 这个工具是做什么的）
    3. parameters: 参数定义（JSON Schema 格式）
    4. fn: 执行函数（上面定义的那些 _xxx 函数）

    参数定义（parameters）的格式：
    {
        "type": "object",
        "properties": {
            "参数名": {
                "type": "类型",
                "description": "参数描述"
            },
            ...
        },
        "required": ["必填参数名", ...]
    }

    返回值：
        配置好的 ToolRegistry 对象
    """
    registry = ToolRegistry()

    # 注册 ReadFile 工具
    registry.register(Tool(
        name="ReadFile",
        description="Read the content of a file. Use line_offset and n_lines for large files.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The path to the file to read"},
                "line_offset": {"type": "integer", "description": "Line number to start reading from", "default": 1},
                "n_lines": {"type": "integer", "description": "Number of lines to read", "default": 1000},
            },
            "required": ["path"],
        },
        fn=_read_file,
    ))

    # 注册 WriteFile 工具
    registry.register(Tool(
        name="WriteFile",
        description="Write content to a file. Creates parent directories automatically.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The path to the file to write"},
                "content": {"type": "string", "description": "The content to write"},
            },
            "required": ["path", "content"],
        },
        fn=_write_file,
    ))

    # 注册 StrReplaceFile 工具
    registry.register(Tool(
        name="StrReplaceFile",
        description="Replace text in a file. old_str must match exactly and be unique.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The path to the file"},
                "old_str": {"type": "string", "description": "The exact text to replace"},
                "new_str": {"type": "string", "description": "The new text"},
            },
            "required": ["path", "old_str", "new_str"],
        },
        fn=_str_replace,
    ))

    # 注册 Shell 工具
    registry.register(Tool(
        name="Shell",
        description="Execute a shell command.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
            },
            "required": ["command"],
        },
        fn=_shell,
    ))

    # 注册 Glob 工具
    registry.register(Tool(
        name="Glob",
        description="Find files by glob pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.py'"},
                "path": {"type": "string", "description": "Directory to search", "default": "."},
            },
            "required": ["pattern"],
        },
        fn=_glob,
    ))

    # 注册 Grep 工具
    registry.register(Tool(
        name="Grep",
        description="Search file contents for a pattern.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern"},
                "path": {"type": "string", "description": "Directory or file to search", "default": "."},
            },
            "required": ["pattern"],
        },
        fn=_grep,
    ))

    # 注册 SearchWeb 工具
    registry.register(Tool(
        name="SearchWeb",
        description="Search the web using DuckDuckGo. Returns search results with titles and URLs.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Maximum number of results (1-10)", "default": 5},
            },
            "required": ["query"],
        },
        fn=_search_web,
    ))

    # 注册 FetchURL 工具
    registry.register(Tool(
        name="FetchURL",
        description="Fetch and extract text content from a URL.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
            },
            "required": ["url"],
        },
        fn=_fetch_url,
    ))

    return registry

# API Key 泄露修复指南

## ⚠️ 紧急情况

如果你的 `.env` 文件已经上传到 GitHub，**立即执行以下步骤**：

---

## 第一步：撤销 API Key（立即执行！）

1. 访问 [Moonshot 控制台](https://platform.moonshot.cn/)
2. 进入 **API Keys** 页面
3. 找到泄露的 Key，点击 **删除** 或 **重新生成**
4. **生成新的 API Key**，稍后更新到本地

> ⚠️ **注意**：即使删除了文件，Git 历史仍然保留，任何人都能在历史中看到你的 Key！

---

## 第二步：清理 Git 历史

### 方法 A：使用脚本（推荐）

```bash
# 运行清理脚本
python check_security.py --clean

# 确认历史已清理
git log --all --full-history -- .env
# 应该没有输出

# 强制推送到远程（会重写历史！）
git push origin main --force
```

### 方法 B：手动操作

```bash
# 1. 从整个 Git 历史中删除 .env
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' \
  --prune-empty --tag-name-filter cat -- --all

# 2. 清理备份（可选）
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 3. 强制推送
git push origin main --force
```

---

## 第三步：更新本地配置

```bash
# 1. 创建新的 .env 文件，填入新 Key
cp .env.example .env
# 编辑 .env，填入新的 API Key

# 2. 验证新 Key 有效
source .env
python -c "from kimi_simplify.config import load_config_from_env; c = load_config_from_env(); print('✅ Key 有效')"
```

---

## 第四步：防止再次泄露

`.gitignore` 已配置好，包含：
```
.env
.env.local
.env.*.local
.kimi_session.json
```

提交更改：
```bash
git add .gitignore SECURITY_FIX.md
git commit -m "security: add .env to gitignore and security docs"
git push
```

---

## 第五步：通知协作者（如果是团队项目）

由于强制推送重写了历史，**所有协作者都需要重新克隆仓库**：

```bash
# 协作者执行
rm -rf kimi-cli-simplify
git clone <repo-url>
```

---

## 检查清单

- [ ] 已在 Moonshot 控制台撤销旧 API Key
- [ ] 已生成新的 API Key
- [ ] 已运行清理脚本或手动清理 Git 历史
- [ ] 已强制推送到远程仓库
- [ ] 已更新本地 `.env` 文件
- [ ] 已验证新 Key 有效
- [ ] 已通知团队重新克隆（如果是协作项目）

---

## 常见问题

### Q: 我已经删除了文件，为什么还要清理历史？
**A**: Git 会保留所有历史版本。即使文件被删除，通过 `git log` 或 GitHub 的 "History" 功能仍然可以查看旧版本。

### Q: 强制推送会有什么影响？
**A**: 会重写 Git 历史。如果有其他人在此基础上工作，他们需要重新克隆。如果是个人项目，无影响。

### Q: 我的仓库是公开的，Key 已经被爬虫抓取了怎么办？
**A**: 立即撤销旧 Key，生成新 Key。清理历史只能减少风险，但公开仓库的 Key 很可能已被记录。

### Q: 如何验证清理是否成功？
**A**: 运行 `python check_security.py`，所有检查项都应显示 ✅。

---

## 预防措施

1. **永远不要把 `.env` 提交到 Git**
2. **使用 `.env.example` 作为模板**，不包含真实 Key
3. **定期运行检测**：`python check_security.py`
4. **使用 GitHub Secret** 管理 CI/CD 中的 Key
5. **启用 API Key 使用监控**，发现异常及时处理

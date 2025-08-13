# 🧠 GRE单词永动机 v2.0 - 安全增强版

**智能化的GRE单词学习系统，基于艾宾浩斯记忆曲线，支持自动推送和Web管理**

## ✨ 核心功能

- 🔐 **安全认证**: 基于session的身份验证保护
- 🧠 **科学复习**: 基于艾宾浩斯记忆曲线的智能推送
- 📱 **移动推送**: 通过ntfy.sh发送手机通知
- 🌐 **Web管理**: 简洁的Web界面，随时添加单词
- 🛡️ **并发安全**: 文件锁机制防止数据竞争
- 🔄 **容错恢复**: 自动重试、备份恢复机制
- 📊 **学习统计**: 直观的学习进度和统计数据
- 🏥 **健康监控**: 系统状态检查和异常诊断

## 📁 项目文件结构

```
gre_word_pusher/
├── 📋 核心应用
│   ├── safe_csv.py           # 安全的CSV文件操作模块
│   ├── app.py               # Flask Web应用（带身份验证）
│   ├── push_words.py        # 智能推送脚本（艾宾浩斯算法）
│   └── health_check.py      # 系统健康检查工具
│
├── 🎨 Web界面
│   └── templates/
│       ├── login.html       # 登录页面
│       ├── index.html       # 主页（添加单词）
│       ├── stats.html       # 学习统计页面
│       └── error.html       # 错误页面
│
├── 🚀 部署工具
│   ├── deploy.sh           # 一键部署脚本
│   ├── verify.sh           # 部署验证脚本
│   ├── gre_app.service     # systemd服务配置
│   └── .env.example        # 环境变量配置模板
│
├── 📖 文档
│   ├── README.md           # 项目说明（本文件）
│   ├── DEPLOY.md           # 详细部署指南
│   └── PRD.md              # 原始需求文档
│
└── 📊 数据文件（运行时生成）
    ├── words.csv           # 单词数据库
    ├── .env                # 环境配置（从.env.example复制）
    ├── logs/              # 日志目录
    └── backups/           # 备份目录
```

## 🚀 快速开始

### 一键部署（推荐）
```bash
# 1. 上传所有文件到VPS的某个目录
# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh

# 3. 验证部署
./verify.sh
```

### 手动部署
详细步骤请参考 [DEPLOY.md](DEPLOY.md)

## 🔧 核心修复内容

### 🔐 安全增强
- ✅ 添加基于session的Web身份验证
- ✅ 环境变量外置化敏感配置
- ✅ 文件权限和系统安全配置

### 🛡️ 并发安全
- ✅ 实现文件锁机制防止CSV竞态条件
- ✅ 原子性写入操作和数据一致性保证
- ✅ 自动备份和故障恢复机制

### 🔄 容错机制  
- ✅ 网络推送重试机制（指数退避）
- ✅ 文件操作异常处理和恢复
- ✅ 系统资源监控和健康检查
- ✅ 详细日志记录和故障诊断

### ⚡ 性能优化
- ✅ 优化重复单词检查算法
- ✅ 智能内存管理和资源限制
- ✅ 缓存机制减少重复计算

## 📱 使用流程

### 1. 配置手机推送
- 安装ntfy应用
- 订阅你的专属主题（在.env文件中设置）

### 2. 添加单词
- 访问Web界面: `http://your-vps-ip:8000`
- 登录（密码在.env文件中）
- 通过表单添加新单词

### 3. 自动推送
- 系统按照艾宾浩斯曲线自动推送
- 默认时间：8:00-22:00，每2小时一次
- 每次推送10-15个需要复习的单词

### 4. 学习统计
- 查看总词数、新词数、复习进度
- 追踪平均复习次数和学习效果

## 🛠 管理命令

```bash
# 服务管理
sudo systemctl start/stop/restart gre_app.service
sudo systemctl status gre_app.service

# 查看日志
sudo journalctl -u gre_app.service -f
tail -f ~/gre_word_pusher/logs/cron.log

# 健康检查
cd ~/gre_word_pusher && python3 health_check.py

# 手动推送测试
cd ~/gre_word_pusher && python3 push_words.py

# 部署验证
cd ~/gre_word_pusher && ./verify.sh
```

## ⚙️ 配置说明

### 环境变量 (.env)
```bash
GRE_SECRET_KEY=your-secret-key          # Flask密钥
GRE_PASSWORD=your-login-password        # Web登录密码
GRE_CSV_PATH=/path/to/words.csv         # 数据文件路径
NTFY_TOPIC=your-unique-topic            # 推送主题
WORDS_PER_PUSH=15                       # 每次推送单词数
```

### 艾宾浩斯记忆曲线间隔
- 新词: 1天后复习
- 第1次复习: 2天后
- 第2次复习: 4天后  
- 第3次复习: 7天后
- 第4次复习: 15天后
- 第5次复习: 30天后
- 第6次及以后: 60天间隔

## 🔒 安全建议

1. **修改默认密码**: 编辑.env文件设置强密码
2. **配置防火墙**: 只开放必要端口(8000)
3. **定期备份**: 备份words.csv文件
4. **监控日志**: 定期查看系统和应用日志
5. **更新系统**: 保持系统和依赖包更新

## 📊 系统要求

- **操作系统**: Linux (Ubuntu 18.04+/CentOS 7+/Debian 9+)
- **Python**: 3.7+
- **内存**: 最小512MB，推荐1GB+
- **磁盘**: 最小1GB可用空间
- **网络**: 能访问ntfy.sh

## 🤝 技术支持

### 常见问题
1. **服务无法启动**: 检查端口占用和文件权限
2. **推送失败**: 验证网络连接和ntfy主题设置
3. **CSV文件损坏**: 使用备份文件恢复
4. **Web界面无法访问**: 检查防火墙和服务状态

### 诊断工具
- 健康检查: `python3 health_check.py`
- 部署验证: `./verify.sh`  
- 服务状态: `systemctl status gre_app.service`

## 📈 后续优化方向

- 📊 数据分析和学习效果追踪
- 🔄 多端同步支持（微信小程序、Telegram Bot）
- 🎯 个性化推荐算法
- 📚 词汇分类和主题管理
- 🌐 多语言支持

---

**🎯 项目目标：通过科学的记忆曲线和便捷的技术手段，帮助你高效掌握GRE词汇！**

*版本: v2.0 安全增强版*  
*最后更新: 2024年*
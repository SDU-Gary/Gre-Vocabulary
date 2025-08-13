# 🚀 GRE单词管理系统 - 快速部署指南

## 📋 系统要求

- **操作系统**: Linux (Ubuntu 18.04+ / CentOS 7+ / Debian 9+)  
- **Python**: 3.7+
- **内存**: 最小 512MB，推荐 1GB+
- **磁盘**: 最小 1GB 可用空间
- **网络**: 可访问 ntfy.sh (用于推送通知)

## ⚡ 一键部署（推荐）

```bash
# 1. 下载项目文件到VPS
git clone <your-repo> gre-word-system
cd gre-word-system

# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh

# 3. 完成！🎉
```

## 📱 手机配置

1. **安装ntfy应用**
   - Android: [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - iOS: [App Store](https://apps.apple.com/app/ntfy/id1625396347)

2. **订阅推送主题**
   - 查看主题名: `cat ~/gre_word_pusher/.env | grep NTFY_TOPIC`
   - 在应用中添加订阅该主题

## 🔐 安全配置

### 1. 修改默认密码
```bash
cd ~/gre_word_pusher
nano .env

# 修改以下项目：
GRE_PASSWORD=你的新密码
GRE_SECRET_KEY=你的随机密钥（建议32位以上）
NTFY_TOPIC=你的私人主题名
```

### 2. 配置防火墙（可选但推荐）
```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp
sudo ufw enable

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 🔧 手动部署（详细步骤）

### 步骤 1: 环境准备
```bash
# 创建项目目录
mkdir -p ~/gre_word_pusher/{templates,logs,backups}
cd ~/gre_word_pusher

# 安装Python依赖
pip3 install Flask gunicorn requests psutil --user
```

### 步骤 2: 文件配置
```bash
# 复制所有项目文件到 ~/gre_word_pusher/
# 包括: safe_csv.py, app.py, push_words.py, health_check.py, templates/

# 创建环境配置
cp .env.example .env
nano .env  # 修改配置
```

### 步骤 3: 数据初始化
```bash
# 创建示例数据文件
cat > words.csv << EOF
ubiquitous,普遍存在的,2024-01-01,2024-01-01,0
meticulous,一丝不苟的,2024-01-01,2024-01-01,0
EOF
```

### 步骤 4: 服务配置
```bash
# 安装systemd服务
sudo cp gre_app.service /etc/systemd/system/
sudo sed -i "s/your_user/$(whoami)/g" /etc/systemd/system/gre_app.service
sudo systemctl daemon-reload
sudo systemctl enable gre_app.service
sudo systemctl start gre_app.service
```

### 步骤 5: 定时任务
```bash
# 添加cron任务
(crontab -l 2>/dev/null; echo "0 8,10,12,14,16,18,20,22 * * * cd ~/gre_word_pusher && python3 push_words.py >> logs/cron.log 2>&1") | crontab -
```

## 📊 验证部署

### 1. 系统健康检查
```bash
cd ~/gre_word_pusher
python3 health_check.py
```

### 2. 服务状态检查
```bash
# 检查Web服务
sudo systemctl status gre_app.service

# 检查服务端口
netstat -tlnp | grep 8000

# 测试Web访问
curl -I http://localhost:8000
```

### 3. 推送测试
```bash
# 手动执行推送
cd ~/gre_word_pusher
python3 push_words.py
```

## 🛠 常见问题解决

### 问题1: 权限错误
```bash
# 修复文件权限
cd ~/gre_word_pusher
chmod 644 *.py words.csv
chmod +x health_check.py
chmod 755 templates/
```

### 问题2: 服务无法启动
```bash
# 查看详细错误
sudo journalctl -u gre_app.service -f

# 检查端口占用
sudo netstat -tlnp | grep 8000

# 手动测试启动
cd ~/gre_word_pusher
gunicorn --workers 1 --bind 0.0.0.0:8000 app:app
```

### 问题3: 推送失败
```bash
# 检查网络连接
curl -I https://ntfy.sh

# 测试推送
curl -d "test message" https://ntfy.sh/你的主题名

# 查看推送日志
tail -f ~/gre_word_pusher/logs/cron.log
```

### 问题4: CSV文件损坏
```bash
# 从备份恢复
cd ~/gre_word_pusher
cp words.csv.backup words.csv

# 或重新创建
python3 -c "
import csv
with open('words.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['word', 'definition', 'added_date', 'last_reviewed_date', 'review_count'])
"
```

## 🔄 日常维护

### 定期任务
```bash
# 每周检查系统健康（建议添加到cron）
0 9 * * 1 cd ~/gre_word_pusher && python3 health_check.py >> logs/health.log 2>&1

# 每月备份数据
0 2 1 * * cp ~/gre_word_pusher/words.csv ~/gre_word_pusher/backups/words_$(date +\%Y\%m\%d).csv
```

### 日志管理
```bash
# 查看应用日志
sudo journalctl -u gre_app.service --since "1 hour ago"

# 查看推送日志
tail -f ~/gre_word_pusher/logs/cron.log

# 清理旧日志（可选）
find ~/gre_word_pusher/logs -name "*.log" -mtime +30 -delete
```

### 更新应用
```bash
# 停止服务
sudo systemctl stop gre_app.service

# 备份数据
cp ~/gre_word_pusher/words.csv ~/gre_word_pusher/words_backup.csv

# 更新代码文件
# ... 复制新文件 ...

# 重启服务
sudo systemctl start gre_app.service

# 验证更新
python3 ~/gre_word_pusher/health_check.py
```

## 📞 获取帮助

### 查看系统状态
- 健康检查: `cd ~/gre_word_pusher && python3 health_check.py`
- 服务状态: `sudo systemctl status gre_app.service`
- 实时日志: `sudo journalctl -u gre_app.service -f`

### 重要文件位置
- 配置文件: `~/gre_word_pusher/.env`
- 数据文件: `~/gre_word_pusher/words.csv`  
- 日志文件: `~/gre_word_pusher/logs/`
- 服务配置: `/etc/systemd/system/gre_app.service`

### 访问信息
- Web界面: `http://你的VPS的IP:8000`
- 默认密码: 在 `.env` 文件中查看 `GRE_PASSWORD`

## 🎯 使用建议

1. **定期备份**: 建议每周备份 `words.csv` 文件
2. **密码安全**: 使用强密码并定期更换
3. **监控日志**: 注意查看系统日志，及时发现问题
4. **网络安全**: 考虑使用VPN或配置防火墙规则
5. **资源监控**: 定期检查磁盘空间和系统负载

---

**🎉 恭喜！现在你拥有了一个安全、可靠、自动化的GRE单词学习系统！**
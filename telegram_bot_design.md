# GRE词汇Telegram Bot 扩展设计

## 🎯 功能规划

### 核心功能
1. **单词管理**
   - `/add <word> <definition>` - 添加新单词
   - `/list` - 查看最近添加的单词
   - `/search <keyword>` - 搜索单词
   - `/delete <word>` - 删除单词

2. **复习系统**
   - `/review` - 手动触发复习推送
   - `/stats` - 查看学习统计
   - `/schedule` - 查看复习计划
   - `/progress` - 查看学习进度

3. **设置管理**
   - `/settings` - 查看当前设置
   - `/set_interval <hours>` - 设置推送间隔
   - `/set_count <number>` - 设置每次推送单词数
   - `/timezone <timezone>` - 设置时区

4. **智能功能**
   - `/remind on/off` - 开启/关闭自动提醒
   - `/difficulty easy/normal/hard` - 调整复习难度
   - `/export` - 导出单词库
   - `/import` - 导入单词库

## 🏗 技术架构

### 1. Bot基础框架
```
telegram_gre_bot/
├── bot.py              # 主Bot程序
├── handlers/           # 命令处理器
│   ├── __init__.py
│   ├── word_handlers.py    # 单词管理命令
│   ├── review_handlers.py  # 复习系统命令
│   └── settings_handlers.py # 设置管理命令
├── services/           # 业务逻辑
│   ├── __init__.py
│   ├── word_service.py     # 单词服务
│   ├── review_service.py   # 复习算法
│   └── notification_service.py # 通知服务
├── models/             # 数据模型
│   ├── __init__.py
│   ├── user.py         # 用户模型
│   └── word.py         # 单词模型
├── database/           # 数据库
│   ├── __init__.py
│   ├── db_manager.py   # 数据库管理
│   └── migrations/     # 数据库迁移
├── utils/              # 工具函数
│   ├── __init__.py
│   ├── validators.py   # 输入验证
│   └── formatters.py   # 消息格式化
├── config/             # 配置文件
│   ├── __init__.py
│   ├── settings.py     # 基础设置
│   └── bot_config.py   # Bot配置
└── requirements.txt    # 依赖包
```

### 2. 数据库设计
```sql
-- 用户表
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    language_code VARCHAR(10) DEFAULT 'zh',
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai',
    words_per_push INTEGER DEFAULT 10,
    push_interval_hours INTEGER DEFAULT 8,
    auto_remind BOOLEAN DEFAULT TRUE,
    difficulty_level VARCHAR(20) DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 单词表
CREATE TABLE words (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    word VARCHAR(255) NOT NULL,
    definition TEXT NOT NULL,
    pronunciation VARCHAR(255),
    example_sentence TEXT,
    category VARCHAR(100),
    difficulty_level INTEGER DEFAULT 1,
    added_date DATE DEFAULT CURRENT_DATE,
    last_reviewed_date DATE,
    review_count INTEGER DEFAULT 0,
    next_review_date DATE,
    mastery_level INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, word)
);

-- 复习记录表
CREATE TABLE review_sessions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    session_date DATE DEFAULT CURRENT_DATE,
    words_reviewed INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    session_duration_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户设置表
CREATE TABLE user_settings (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    notification_time_1 TIME DEFAULT '08:00:00',
    notification_time_2 TIME DEFAULT '12:00:00',
    notification_time_3 TIME DEFAULT '18:00:00',
    notification_time_4 TIME DEFAULT '21:00:00',
    weekend_schedule BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🚀 实现步骤

### 阶段1: 基础Bot框架 (1-2周)
1. **环境搭建**
   - 创建Telegram Bot Token
   - 搭建Python环境
   - 配置数据库（PostgreSQL/SQLite）

2. **基础功能**
   - 用户注册/登录
   - 基础命令响应
   - 数据库连接

### 阶段2: 核心功能开发 (2-3周)
1. **单词管理**
   - 添加/删除/搜索单词
   - 数据验证和去重
   - 批量导入功能

2. **复习系统**
   - 艾宾浩斯算法移植
   - 定时推送机制
   - 复习反馈收集

### 阶段3: 高级功能 (2-3周)
1. **智能推荐**
   - 基于用户行为的个性化推荐
   - 难度自适应调整
   - 学习效果分析

2. **多媒体支持**
   - 语音发音
   - 图片示例
   - 交互式按钮

### 阶段4: 优化完善 (1-2周)
1. **性能优化**
   - 数据库查询优化
   - 缓存机制
   - 并发处理

2. **用户体验**
   - 多语言支持
   - 错误处理优化
   - 使用统计分析

## 🛠 技术栈推荐

### 核心技术
- **Bot框架**: `python-telegram-bot` (推荐) 或 `aiogram`
- **数据库**: PostgreSQL + SQLAlchemy ORM
- **任务调度**: APScheduler 或 Celery
- **缓存**: Redis
- **部署**: Docker + Docker Compose

### 依赖包
```txt
python-telegram-bot==20.7
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
apscheduler==3.10.4
redis==5.0.1
python-dotenv==1.0.0
alembic==1.13.1
requests==2.31.0
```

## 🔄 迁移策略

### 从现有系统迁移
1. **数据迁移**
   ```python
   # 从CSV迁移到数据库
   def migrate_csv_to_db():
       # 读取现有words.csv
       # 转换为数据库格式
       # 保留复习历史和进度
   ```

2. **用户平滑过渡**
   - 保持现有ntfy推送并行运行
   - 逐步引导用户使用Bot
   - 提供数据导出/导入功能

### 共存方案
```python
# 双推送机制
class NotificationService:
    def send_notification(self, user_id, words):
        # 优先发送Telegram消息
        try:
            self.send_telegram_message(user_id, words)
        except:
            # 降级到ntfy推送
            self.send_ntfy_notification(words)
```

## 📱 用户界面设计

### 主菜单界面
```
🧠 GRE词汇助手

📚 单词管理
   ├── ➕ 添加单词
   ├── 📋 单词列表  
   ├── 🔍 搜索单词
   └── 🗑️ 删除单词

📖 复习系统
   ├── 🎯 开始复习
   ├── 📊 学习统计
   ├── 📅 复习计划
   └── 📈 学习进度

⚙️ 设置
   ├── 🔔 推送设置
   ├── ⏰ 时间设置
   ├── 🎚️ 难度调整
   └── 🌐 语言设置
```

### 互动式复习
```
📖 今日复习 (3/10)

单词: ubiquitous
定义: 普遍存在的，无处不在的

你记得这个单词吗？
[✅ 记得] [❌ 忘了] [🤔 模糊]

例句: Social media has become ubiquitous in modern life.
```

## 🔐 安全考虑

### 数据安全
- 用户数据加密存储
- API访问频率限制
- 输入验证和SQL注入防护

### 隐私保护
- 最小化数据收集
- 用户数据导出/删除功能
- GDPR合规性

## 📈 监控和分析

### 关键指标
- 用户活跃度 (DAU/MAU)
- 单词掌握率
- 复习完成率
- 用户留存率

### 日志系统
```python
import logging

# 用户行为日志
logger.info(f"User {user_id} added word: {word}")
logger.info(f"User {user_id} completed review session: {session_stats}")

# 性能监控
logger.info(f"Database query time: {query_time}ms")
logger.info(f"Bot response time: {response_time}ms")
```

## 🚀 部署方案

### Docker部署
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "bot.py"]
```

### Docker Compose
```yaml
# docker-compose.yml
version: '3.8'
services:
  bot:
    build: .
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: gre_bot
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    
volumes:
  postgres_data:
```

## 💡 未来扩展方向

### 功能扩展
1. **多平台支持**: 微信小程序、Web应用
2. **社交功能**: 好友对战、排行榜
3. **AI集成**: GPT辅助生成例句、智能复习建议
4. **多语言词汇**: 扩展到托福、雅思、四六级等

### 商业化考虑
1. **免费版**: 基础功能 + 广告
2. **高级版**: 无广告 + 高级统计 + 个性化服务
3. **机构版**: 批量管理 + 学习分析 + 定制功能
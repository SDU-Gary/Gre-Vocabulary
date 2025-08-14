#!/bin/bash
# Telegram Bot 自动化设置脚本

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

PROJECT_DIR="/root/gre_word_pusher"

echo "🤖 GRE Telegram Bot 设置向导"
echo "=================================="

# 1. 检查Python环境
info "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    error "Python3 未安装"
    exit 1
fi

python_version=$(python3 --version | cut -d' ' -f2)
info "Python版本: $python_version"

# 2. 安装依赖
info "安装Telegram Bot依赖包..."
pip3 install python-telegram-bot==20.7 --quiet
success "依赖包安装完成"

# 3. 创建Bot配置文件
info "创建Bot配置..."

# 检查是否已有Bot Token
if [[ -f "$PROJECT_DIR/.env" ]]; then
    if grep -q "TELEGRAM_BOT_TOKEN" "$PROJECT_DIR/.env"; then
        success "发现现有的Bot Token配置"
    else
        warning "需要添加Telegram Bot Token到.env文件"
        echo "" >> "$PROJECT_DIR/.env"
        echo "# Telegram Bot 配置" >> "$PROJECT_DIR/.env"
        echo "TELEGRAM_BOT_TOKEN=" >> "$PROJECT_DIR/.env"
        echo "TELEGRAM_USER_ID=" >> "$PROJECT_DIR/.env"
    fi
else
    warning ".env文件不存在，创建新的配置文件"
    cat > "$PROJECT_DIR/.env" << 'EOF'
# GRE推送系统配置
GRE_SECRET_KEY=your-secret-key-here
GRE_PASSWORD=your-password-here
GRE_CSV_PATH=/root/gre_word_pusher/words.csv
NTFY_TOPIC=your-ntfy-topic-here
WORDS_PER_PUSH=15

# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=
EOF
fi

# 4. 创建Bot启动脚本
info "创建Bot启动脚本..."
cat > "$PROJECT_DIR/start_telegram_bot.py" << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE Telegram Bot 启动脚本
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/telegram_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def load_env_file():
    """加载环境变量"""
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def main():
    """主函数"""
    # 加载环境变量
    load_env_file()
    
    # 检查Bot Token
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token or bot_token == '':
        print("❌ 请在.env文件中设置TELEGRAM_BOT_TOKEN")
        print("💡 使用 @BotFather 创建Bot并获取Token")
        return
    
    print(f"🤖 启动GRE Telegram Bot...")
    print(f"📁 项目目录: {project_root}")
    
    try:
        # 导入Bot模块
        from telegram_bot_enhanced import GREBot
        
        # 创建并启动Bot
        bot = GREBot(project_root)
        bot.run()
        
    except ImportError as e:
        print(f"❌ 导入Bot模块失败: {e}")
        print("请确保telegram_bot_enhanced.py文件存在")
    except Exception as e:
        logger.error(f"Bot启动失败: {e}")
        print(f"❌ Bot启动失败: {e}")

if __name__ == '__main__':
    main()
EOF

chmod +x "$PROJECT_DIR/start_telegram_bot.py"

# 5. 创建systemd服务文件
info "创建systemd服务配置..."
sudo tee /etc/systemd/system/gre-telegram-bot.service > /dev/null << EOF
[Unit]
Description=GRE Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR
ExecStart=/usr/bin/python3 start_telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/telegram_bot.log
StandardError=append:$PROJECT_DIR/logs/telegram_bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# 6. 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 7. 创建数据迁移脚本
info "创建数据迁移脚本..."
cat > "$PROJECT_DIR/migrate_csv_to_telegram.py" << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV数据迁移到Telegram Bot数据库
"""

import csv
import sqlite3
import os
from datetime import datetime, date, timedelta
from pathlib import Path

def load_env():
    """加载环境变量"""
    env_file = Path(__file__).parent / '.env'
    config = {}
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    return config

def calculate_next_review_date(review_count, last_reviewed_date=None):
    """计算下次复习日期"""
    intervals = [1, 2, 4, 7, 15, 30, 60]
    
    if review_count == 0:
        # 新单词，1天后复习
        return (date.today() + timedelta(days=1)).isoformat()
    
    if last_reviewed_date:
        try:
            last_date = datetime.strptime(last_reviewed_date, '%Y-%m-%d').date()
            interval_index = min(review_count, len(intervals) - 1)
            next_date = last_date + timedelta(days=intervals[interval_index])
            return next_date.isoformat()
        except ValueError:
            pass
    
    # 默认情况
    return (date.today() + timedelta(days=1)).isoformat()

def migrate_data(csv_path, db_path, default_user_id=None):
    """迁移CSV数据到SQLite数据库"""
    
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return False
    
    # 如果没有指定用户ID，使用默认值
    if not default_user_id:
        config = load_env()
        default_user_id = config.get('TELEGRAM_USER_ID', '123456789')
        if default_user_id == '':
            default_user_id = '123456789'
        default_user_id = int(default_user_id)
    
    # 初始化数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建用户（如果不存在）
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, first_name, created_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (default_user_id, "CSV导入用户"))
    
    # 读取CSV文件并迁移
    migrated_count = 0
    skipped_count = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            for row_num, row in enumerate(reader, 1):
                if len(row) < 5:
                    print(f"⚠️ 跳过第{row_num}行，数据不完整: {row}")
                    skipped_count += 1
                    continue
                
                word, definition, added_date, last_reviewed_date, review_count = row[:5]
                
                try:
                    review_count = int(review_count)
                    
                    # 计算下次复习日期
                    next_review_date = calculate_next_review_date(
                        review_count, 
                        last_reviewed_date if last_reviewed_date else None
                    )
                    
                    # 插入数据
                    cursor.execute('''
                        INSERT OR IGNORE INTO words 
                        (user_id, word, definition, added_date, last_reviewed_date, 
                         review_count, next_review_date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        default_user_id,
                        word.lower().strip(),
                        definition.strip(),
                        added_date,
                        last_reviewed_date if last_reviewed_date else None,
                        review_count,
                        next_review_date
                    ))
                    
                    if cursor.rowcount > 0:
                        migrated_count += 1
                    else:
                        skipped_count += 1
                        
                except (ValueError, sqlite3.Error) as e:
                    print(f"⚠️ 跳过第{row_num}行，处理失败: {e}")
                    skipped_count += 1
                    continue
    
        conn.commit()
        
        print(f"✅ 数据迁移完成!")
        print(f"   成功迁移: {migrated_count} 个单词")
        print(f"   跳过: {skipped_count} 个记录")
        print(f"   目标用户ID: {default_user_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        return False
    finally:
        conn.close()

def main():
    """主函数"""
    print("📦 CSV数据迁移工具")
    print("="*30)
    
    project_dir = Path(__file__).parent
    csv_path = project_dir / "words.csv"
    db_path = project_dir / "telegram_bot.db"
    
    print(f"CSV文件: {csv_path}")
    print(f"数据库文件: {db_path}")
    
    config = load_env()
    user_id = config.get('TELEGRAM_USER_ID')
    
    if user_id and user_id != '':
        try:
            user_id = int(user_id)
            print(f"目标用户ID: {user_id}")
        except ValueError:
            print("⚠️ 用户ID格式无效，使用默认值")
            user_id = None
    else:
        print("⚠️ 未配置TELEGRAM_USER_ID，使用默认值")
        user_id = None
    
    success = migrate_data(str(csv_path), str(db_path), user_id)
    
    if success:
        print("\n🎉 迁移完成！现在可以启动Telegram Bot了")
    else:
        print("\n❌ 迁移失败，请检查错误信息")

if __name__ == '__main__':
    main()
EOF

chmod +x "$PROJECT_DIR/migrate_csv_to_telegram.py"

# 8. 显示下一步操作
echo
success "Telegram Bot 基础设置完成！"
echo
echo "🔧 接下来需要完成以下步骤:"
echo
echo "1️⃣ 创建Telegram Bot:"
echo "   • 在Telegram中搜索 @BotFather"
echo "   • 发送 /newbot"
echo "   • 按提示设置Bot名称和用户名"
echo "   • 复制获得的Bot Token"
echo
echo "2️⃣ 配置Bot Token:"
echo "   • 编辑 $PROJECT_DIR/.env 文件"
echo "   • 设置 TELEGRAM_BOT_TOKEN=你的Bot Token"
echo "   • 设置 TELEGRAM_USER_ID=你的Telegram用户ID"
echo
echo "3️⃣ 获取用户ID:"
echo "   • 在Telegram中搜索 @userinfobot"
echo "   • 发送任意消息获取你的用户ID"
echo
echo "4️⃣ 启动Bot:"
echo "   • cd $PROJECT_DIR"
echo "   • python3 start_telegram_bot.py"
echo
warning "⚠️  还需要创建 telegram_bot_enhanced.py 文件才能启动Bot"
echo "   请等待下一个文件创建完成"
echo
echo "📖 详细说明文档: telegram_bot_design.md"
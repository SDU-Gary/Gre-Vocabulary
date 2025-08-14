#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE词汇Telegram Bot - 启动模板
基于现有GRE推送系统的Telegram Bot扩展
"""

import logging
import os
import sqlite3
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 配置
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
DATABASE_PATH = '/root/gre_word_pusher/telegram_bot.db'
CSV_PATH = '/root/gre_word_pusher/words.csv'

# 艾宾浩斯记忆曲线间隔（天）
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30, 60]

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                language_code TEXT DEFAULT 'zh',
                timezone TEXT DEFAULT 'Asia/Shanghai',
                words_per_push INTEGER DEFAULT 10,
                push_interval_hours INTEGER DEFAULT 8,
                auto_remind BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 单词表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                word TEXT NOT NULL,
                definition TEXT NOT NULL,
                pronunciation TEXT,
                example_sentence TEXT,
                added_date DATE DEFAULT CURRENT_DATE,
                last_reviewed_date DATE,
                review_count INTEGER DEFAULT 0,
                next_review_date DATE,
                mastery_level INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, word)
            )
        ''')
        
        # 复习记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_date DATE DEFAULT CURRENT_DATE,
                words_reviewed INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """获取用户信息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        conn.close()
        return dict(user) if user else None
    
    def create_or_update_user(self, user_data: Dict):
        """创建或更新用户"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, language_code, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            user_data['user_id'],
            user_data.get('username'),
            user_data.get('first_name'),
            user_data.get('language_code', 'zh')
        ))
        
        conn.commit()
        conn.close()
    
    def add_word(self, user_id: int, word: str, definition: str) -> bool:
        """添加单词"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 计算下次复习日期（新单词1天后复习）
            next_review = (datetime.now().date() + timedelta(days=1)).isoformat()
            
            cursor.execute('''
                INSERT INTO words (user_id, word, definition, next_review_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, word.lower().strip(), definition.strip(), next_review))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # 单词已存在
            return False
        except Exception as e:
            logger.error(f"添加单词失败: {e}")
            return False
    
    def get_words_for_review(self, user_id: int, limit: int = 10) -> List[Dict]:
        """获取需要复习的单词"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        
        cursor.execute('''
            SELECT * FROM words 
            WHERE user_id = ? AND (
                review_count = 0 OR 
                (next_review_date IS NOT NULL AND next_review_date <= ?)
            )
            ORDER BY 
                CASE WHEN review_count = 0 THEN 0 ELSE 1 END,
                next_review_date ASC
            LIMIT ?
        ''', (user_id, today, limit))
        
        words = cursor.fetchall()
        conn.close()
        
        return [dict(word) for word in words]
    
    def update_word_review(self, word_id: int, mastered: bool = True):
        """更新单词复习状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取当前复习次数
        cursor.execute('SELECT review_count FROM words WHERE id = ?', (word_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return
        
        current_review_count = result[0]
        new_review_count = current_review_count + 1
        
        # 计算下次复习日期
        if mastered:
            interval_index = min(new_review_count, len(REVIEW_INTERVALS) - 1)
            interval_days = REVIEW_INTERVALS[interval_index]
        else:
            # 如果没掌握，重置到较短间隔
            interval_days = REVIEW_INTERVALS[0]
            new_review_count = max(1, current_review_count)
        
        next_review_date = (datetime.now().date() + timedelta(days=interval_days)).isoformat()
        
        cursor.execute('''
            UPDATE words 
            SET review_count = ?, 
                last_reviewed_date = CURRENT_DATE,
                next_review_date = ?,
                mastery_level = CASE WHEN ? THEN mastery_level + 1 ELSE mastery_level END
            WHERE id = ?
        ''', (new_review_count, next_review_date, mastered, word_id))
        
        conn.commit()
        conn.close()
    
    def get_user_stats(self, user_id: int) -> Dict:
        """获取用户学习统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总单词数
        cursor.execute('SELECT COUNT(*) FROM words WHERE user_id = ?', (user_id,))
        total_words = cursor.fetchone()[0]
        
        # 新单词数
        cursor.execute('SELECT COUNT(*) FROM words WHERE user_id = ? AND review_count = 0', (user_id,))
        new_words = cursor.fetchone()[0]
        
        # 需要复习的单词数
        today = date.today().isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM words 
            WHERE user_id = ? AND next_review_date <= ?
        ''', (user_id, today))
        due_words = cursor.fetchone()[0]
        
        # 掌握程度高的单词数
        cursor.execute('SELECT COUNT(*) FROM words WHERE user_id = ? AND mastery_level >= 3', (user_id,))
        mastered_words = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_words': total_words,
            'new_words': new_words,
            'due_words': due_words,
            'mastered_words': mastered_words
        }

class GREBot:
    """GRE词汇学习Bot"""
    
    def __init__(self):
        self.db = DatabaseManager(DATABASE_PATH)
        self.user_states: Dict[int, Dict] = {}  # 用户状态管理
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始命令"""
        user = update.effective_user
        
        # 保存用户信息
        self.db.create_or_update_user({
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'language_code': user.language_code
        })
        
        welcome_text = f"""
🧠 欢迎使用GRE词汇学习助手！

你好 {user.first_name}！我可以帮你：

📚 单词管理
• /add - 添加新单词
• /list - 查看单词列表
• /search - 搜索单词

📖 复习系统  
• /review - 开始复习
• /stats - 查看学习统计

⚙️ 设置
• /settings - 查看设置
• /help - 查看帮助

开始添加你的第一个单词吧！使用 /add 命令。
        """
        
        await update.message.reply_text(welcome_text.strip())
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
🤖 GRE词汇助手使用指南

📝 添加单词:
/add ubiquitous 普遍存在的，无处不在的

📋 查看单词:
/list - 显示最近添加的单词
/list 20 - 显示最近20个单词

🔍 搜索单词:
/search ubiquitous
/search 普遍 (支持中文搜索)

📖 开始复习:
/review - 开始今日复习
/review 5 - 复习5个单词

📊 学习统计:
/stats - 查看学习进度

⚙️ 其他功能:
/settings - 查看当前设置
/export - 导出单词库
/delete <单词> - 删除单词

💡 提示:
• 添加单词时，单词和释义用空格分隔
• 支持中英文搜索
• 复习时会根据艾宾浩斯记忆曲线智能安排
        """
        
        await update.message.reply_text(help_text.strip())
    
    async def add_word_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始添加单词流程"""
        if context.args and len(context.args) >= 2:
            # 直接添加模式: /add word definition
            word = context.args[0]
            definition = ' '.join(context.args[1:])
            await self.add_word_complete(update, context, word, definition)
        else:
            # 交互式添加模式
            self.user_states[update.effective_user.id] = {'action': 'adding_word', 'step': 'word'}
            await update.message.reply_text("📝 请输入要添加的英文单词:")
    
    async def add_word_complete(self, update: Update, context: ContextTypes.DEFAULT_TYPE, word: str, definition: str):
        """完成添加单词"""
        user_id = update.effective_user.id
        
        if self.db.add_word(user_id, word, definition):
            await update.message.reply_text(f"✅ 单词添加成功！\n\n📖 {word}\n💭 {definition}")
        else:
            await update.message.reply_text(f"❌ 单词已存在或添加失败: {word}")
        
        # 清除用户状态
        self.user_states.pop(user_id, None)
    
    async def list_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """列出单词"""
        user_id = update.effective_user.id
        limit = 10
        
        if context.args:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 50))  # 限制在1-50之间
            except ValueError:
                await update.message.reply_text("❌ 请输入有效的数字")
                return
        
        # 获取最近添加的单词
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT word, definition, added_date, review_count 
            FROM words 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        words = cursor.fetchall()
        conn.close()
        
        if not words:
            await update.message.reply_text("📭 你还没有添加任何单词。\n\n使用 /add 命令添加第一个单词吧！")
            return
        
        text_lines = [f"📚 你的单词库 (最近{len(words)}个):\n"]
        
        for i, word in enumerate(words, 1):
            review_status = "🆕 新词" if word['review_count'] == 0 else f"📖 复习{word['review_count']}次"
            text_lines.append(f"{i}. **{word['word']}**")
            text_lines.append(f"   💭 {word['definition']}")
            text_lines.append(f"   📅 {word['added_date']} | {review_status}\n")
        
        text_lines.append(f"💡 使用 /review 开始复习，/add 添加更多单词")
        
        await update.message.reply_text('\n'.join(text_lines), parse_mode='Markdown')
    
    async def start_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始复习"""
        user_id = update.effective_user.id
        limit = 10
        
        if context.args:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 20))
            except ValueError:
                limit = 10
        
        words = self.db.get_words_for_review(user_id, limit)
        
        if not words:
            await update.message.reply_text("🎉 太棒了！今天没有需要复习的单词。\n\n你可以:\n• /add 添加新单词\n• /stats 查看学习统计")
            return
        
        # 设置复习状态
        self.user_states[user_id] = {
            'action': 'reviewing',
            'words': words,
            'current_index': 0,
            'correct_count': 0
        }
        
        await self.show_review_word(update, context)
    
    async def show_review_word(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """显示复习单词"""
        user_id = update.effective_user.id
        state = self.user_states.get(user_id, {})
        
        if state.get('action') != 'reviewing':
            await update.message.reply_text("❌ 请先使用 /review 开始复习")
            return
        
        words = state['words']
        current_index = state['current_index']
        
        if current_index >= len(words):
            # 复习结束
            await self.finish_review(update, context)
            return
        
        word_data = words[current_index]
        progress = f"({current_index + 1}/{len(words)})"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ 记得", callback_data=f"review_correct_{word_data['id']}"),
                InlineKeyboardButton("❌ 忘了", callback_data=f"review_wrong_{word_data['id']}")
            ],
            [InlineKeyboardButton("🔍 查看释义", callback_data=f"review_show_{word_data['id']}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"📖 复习单词 {progress}\n\n**{word_data['word']}**\n\n你还记得这个单词的意思吗？"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_review_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理复习回调"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        state = self.user_states.get(user_id, {})
        
        if state.get('action') != 'reviewing':
            await query.edit_message_text("❌ 复习会话已过期，请重新开始")
            return
        
        action_parts = query.data.split('_')
        action = action_parts[1]  # correct, wrong, show
        word_id = int(action_parts[2])
        
        words = state['words']
        current_index = state['current_index']
        word_data = words[current_index]
        
        if action == 'show':
            # 显示释义
            text = f"📖 单词释义\n\n**{word_data['word']}**\n💭 {word_data['definition']}\n\n你记得了吗？"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ 记得", callback_data=f"review_correct_{word_id}"),
                    InlineKeyboardButton("❌ 忘了", callback_data=f"review_wrong_{word_id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        elif action in ['correct', 'wrong']:
            # 处理复习结果
            mastered = (action == 'correct')
            self.db.update_word_review(word_id, mastered)
            
            if mastered:
                state['correct_count'] += 1
            
            # 移动到下一个单词
            state['current_index'] += 1
            self.user_states[user_id] = state
            
            await self.show_review_word(update, context)
    
    async def finish_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """完成复习"""
        user_id = update.effective_user.id
        state = self.user_states.get(user_id, {})
        
        total_words = len(state.get('words', []))
        correct_count = state.get('correct_count', 0)
        accuracy = (correct_count / total_words * 100) if total_words > 0 else 0
        
        # 记录复习会话
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO review_sessions (user_id, words_reviewed, correct_answers)
            VALUES (?, ?, ?)
        ''', (user_id, total_words, correct_count))
        conn.commit()
        conn.close()
        
        # 清除状态
        self.user_states.pop(user_id, None)
        
        text = f"""
🎉 复习完成！

📊 本次复习统计:
• 复习单词: {total_words} 个
• 记得单词: {correct_count} 个  
• 准确率: {accuracy:.1f}%

💡 被遗忘的单词会缩短复习间隔
记住的单词将按照记忆曲线安排下次复习

继续加油！ 🚀
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text.strip())
        else:
            await update.message.reply_text(text.strip())
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """显示学习统计"""
        user_id = update.effective_user.id
        stats = self.db.get_user_stats(user_id)
        
        # 计算掌握率
        mastery_rate = 0
        if stats['total_words'] > 0:
            mastery_rate = (stats['mastered_words'] / stats['total_words']) * 100
        
        text = f"""
📊 你的学习统计

📚 单词库状态:
• 总单词数: {stats['total_words']} 个
• 新单词: {stats['new_words']} 个
• 待复习: {stats['due_words']} 个
• 已掌握: {stats['mastered_words']} 个

📈 学习进度:
• 掌握率: {mastery_rate:.1f}%

💡 建议:
        """
        
        if stats['due_words'] > 0:
            text += f"有 {stats['due_words']} 个单词需要复习，使用 /review 开始复习吧！"
        elif stats['new_words'] > 0:
            text += f"有 {stats['new_words']} 个新单词等待学习，使用 /review 开始学习吧！"
        else:
            text += "今天的学习任务完成了！可以添加新单词或休息一下。"
        
        await update.message.reply_text(text.strip())
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理普通消息（用于交互式添加单词）"""
        user_id = update.effective_user.id
        state = self.user_states.get(user_id, {})
        
        if state.get('action') == 'adding_word':
            if state.get('step') == 'word':
                # 获取单词
                word = update.message.text.strip()
                if not word or ' ' in word:
                    await update.message.reply_text("❌ 请输入一个有效的英文单词（不含空格）:")
                    return
                
                state['word'] = word
                state['step'] = 'definition'
                self.user_states[user_id] = state
                
                await update.message.reply_text(f"📖 单词: **{word}**\n\n💭 请输入中文释义:", parse_mode='Markdown')
                
            elif state.get('step') == 'definition':
                # 获取释义
                definition = update.message.text.strip()
                if not definition:
                    await update.message.reply_text("❌ 请输入有效的释义:")
                    return
                
                word = state['word']
                await self.add_word_complete(update, context, word, definition)
        else:
            # 普通消息，提供帮助
            await update.message.reply_text("💡 使用 /help 查看可用命令，或 /add 添加新单词")

def main():
    """主函数"""
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ 请设置TELEGRAM_BOT_TOKEN环境变量")
        return
    
    # 创建Bot实例
    bot = GREBot()
    
    # 创建Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 添加处理器
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("add", bot.add_word_start))
    application.add_handler(CommandHandler("list", bot.list_words))
    application.add_handler(CommandHandler("review", bot.start_review))
    application.add_handler(CommandHandler("stats", bot.show_stats))
    
    # 回调查询处理器
    application.add_handler(CallbackQueryHandler(bot.handle_review_callback, pattern=r'^review_'))
    
    # 消息处理器（用于交互式添加）
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # 启动Bot
    print("🤖 GRE词汇Bot启动中...")
    application.run_polling()

if __name__ == '__main__':
    main()
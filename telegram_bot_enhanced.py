#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE词汇Telegram Bot - 增强版
完整的Telegram Bot实现，包含所有核心功能
"""

import logging
import os
import sqlite3
import json
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                difficulty_rating INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                session_duration_seconds INTEGER DEFAULT 0,
                session_type TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 用户设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                notification_enabled BOOLEAN DEFAULT 1,
                daily_goal INTEGER DEFAULT 20,
                preferred_review_time TEXT DEFAULT '09:00',
                difficulty_preference TEXT DEFAULT 'adaptive',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")
    
    def create_or_update_user(self, user_data: Dict):
        """创建或更新用户"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, language_code, last_active, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (
            user_data['user_id'],
            user_data.get('username'),
            user_data.get('first_name'),
            user_data.get('language_code', 'zh')
        ))
        
        # 创建用户偏好设置
        cursor.execute('''
            INSERT OR IGNORE INTO user_preferences (user_id)
            VALUES (?)
        ''', (user_data['user_id'],))
        
        conn.commit()
        conn.close()
    
    def add_word(self, user_id: int, word: str, definition: str, pronunciation: str = None) -> bool:
        """添加单词"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 计算下次复习日期（新单词1天后复习）
            next_review = (date.today() + timedelta(days=1)).isoformat()
            
            cursor.execute('''
                INSERT INTO words (user_id, word, definition, pronunciation, next_review_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, word.lower().strip(), definition.strip(), pronunciation, next_review))
            
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
                next_review_date ASC,
                difficulty_rating DESC
            LIMIT ?
        ''', (user_id, today, limit))
        
        words = cursor.fetchall()
        conn.close()
        
        return [dict(word) for word in words]
    
    def update_word_review(self, word_id: int, mastered: bool = True, difficulty: int = None):
        """更新单词复习状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取当前复习次数
        cursor.execute('SELECT review_count, difficulty_rating FROM words WHERE id = ?', (word_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return
        
        current_review_count, current_difficulty = result
        new_review_count = current_review_count + 1
        
        # 更新难度评级
        if difficulty is not None:
            new_difficulty = difficulty
        else:
            # 根据掌握情况自动调整难度
            if mastered:
                new_difficulty = max(1, current_difficulty - 1)
            else:
                new_difficulty = min(5, current_difficulty + 1)
        
        # 计算下次复习日期
        if mastered:
            interval_index = min(new_review_count, len(REVIEW_INTERVALS) - 1)
            interval_days = REVIEW_INTERVALS[interval_index]
        else:
            # 如果没掌握，使用较短间隔
            interval_days = max(1, REVIEW_INTERVALS[0] // 2)
            new_review_count = max(1, current_review_count)
        
        next_review_date = (date.today() + timedelta(days=interval_days)).isoformat()
        
        cursor.execute('''
            UPDATE words 
            SET review_count = ?, 
                last_reviewed_date = CURRENT_DATE,
                next_review_date = ?,
                difficulty_rating = ?,
                mastery_level = CASE WHEN ? THEN mastery_level + 1 ELSE mastery_level END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_review_count, next_review_date, new_difficulty, mastered, word_id))
        
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
        
        # 今日复习统计
        cursor.execute('''
            SELECT COALESCE(SUM(words_reviewed), 0), COALESCE(SUM(correct_answers), 0)
            FROM review_sessions 
            WHERE user_id = ? AND session_date = CURRENT_DATE
        ''', (user_id,))
        today_reviewed, today_correct = cursor.fetchone()
        
        # 连续学习天数
        cursor.execute('''
            SELECT COUNT(DISTINCT session_date) as streak
            FROM review_sessions 
            WHERE user_id = ? AND session_date >= date('now', '-30 days')
        ''', (user_id,))
        learning_streak = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_words': total_words,
            'new_words': new_words,
            'due_words': due_words,
            'mastered_words': mastered_words,
            'today_reviewed': today_reviewed,
            'today_correct': today_correct,
            'learning_streak': learning_streak,
            'mastery_rate': (mastered_words / total_words * 100) if total_words > 0 else 0
        }
    
    def search_words(self, user_id: int, query: str, limit: int = 10) -> List[Dict]:
        """搜索单词"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 支持中英文搜索
        search_query = f"%{query.lower()}%"
        
        cursor.execute('''
            SELECT * FROM words 
            WHERE user_id = ? AND (
                LOWER(word) LIKE ? OR 
                LOWER(definition) LIKE ? OR
                LOWER(pronunciation) LIKE ?
            )
            ORDER BY 
                CASE WHEN LOWER(word) = LOWER(?) THEN 1 ELSE 2 END,
                word
            LIMIT ?
        ''', (user_id, search_query, search_query, search_query, query.lower(), limit))
        
        words = cursor.fetchall()
        conn.close()
        
        return [dict(word) for word in words]
    
    def delete_word(self, user_id: int, word: str) -> bool:
        """删除单词"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM words 
                WHERE user_id = ? AND LOWER(word) = LOWER(?)
            ''', (user_id, word.strip()))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            return deleted
        except Exception as e:
            logger.error(f"删除单词失败: {e}")
            return False
    
    def get_recent_words(self, user_id: int, limit: int = 10) -> List[Dict]:
        """获取最近添加的单词"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM words 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        words = cursor.fetchall()
        conn.close()
        
        return [dict(word) for word in words]

class GREBot:
    """GRE词汇学习Bot"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.db_path = self.project_root / "telegram_bot.db"
        self.db = DatabaseManager(str(self.db_path))
        self.user_states: Dict[int, Dict] = {}  # 用户状态管理
        
        # 加载配置
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("请设置TELEGRAM_BOT_TOKEN环境变量")
        
        logger.info(f"Bot初始化完成，数据库路径: {self.db_path}")
    
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
🧠 **欢迎使用GRE词汇学习助手！**

你好 {user.first_name}！我是你的专属GRE词汇学习伙伴 🤖

**✨ 我能帮你做什么：**

📚 **单词管理**
• /add - 添加新单词
• /list - 浏览单词库
• /search - 搜索单词

📖 **智能复习**  
• /review - 开始今日复习
• /stats - 学习统计分析

⚙️ **个人设置**
• /settings - 个人偏好设置
• /export - 导出单词数据

💡 **使用提示**
• 基于艾宾浩斯记忆曲线智能安排复习
• 支持中英文搜索和交互
• 记录详细学习数据和进度

开始你的GRE词汇之旅吧！使用 /add 添加第一个单词 📝
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📝 添加单词", callback_data="quick_add"),
                InlineKeyboardButton("📖 开始复习", callback_data="quick_review")
            ],
            [
                InlineKeyboardButton("📊 学习统计", callback_data="quick_stats"),
                InlineKeyboardButton("❓ 帮助指南", callback_data="quick_help")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text.strip(), 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
📖 **GRE词汇助手完整指南**

**📝 添加单词**
• `/add word definition` - 直接添加
• `/add` - 交互式添加模式

*示例：*
`/add ubiquitous 普遍存在的，无处不在的`

**📋 管理单词**
• `/list [数量]` - 查看最近添加的单词
• `/search 关键词` - 搜索单词（支持中英文）
• `/delete 单词` - 删除指定单词

**📖 复习系统**
• `/review [数量]` - 开始复习会话
• `/stats` - 详细学习统计
• `/progress` - 学习进度分析

**⚙️ 设置与工具**
• `/settings` - 个人偏好设置
• `/export` - 导出所有单词数据
• `/import` - 批量导入单词

**🎯 复习机制**
• 基于艾宾浩斯记忆曲线
• 智能调整复习间隔
• 追踪掌握程度
• 个性化难度调节

**💡 实用技巧**
• 添加发音信息：`/add word definition [pronunciation]`
• 搜索支持模糊匹配
• 复习时诚实反馈掌握情况
• 定期查看统计数据调整学习策略

有问题随时问我！ 🤗
        """
        
        await update.message.reply_text(help_text.strip(), parse_mode='Markdown')
    
    async def add_word_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """添加单词命令"""
        if context.args and len(context.args) >= 2:
            # 直接添加模式
            word = context.args[0]
            definition = ' '.join(context.args[1:])
            pronunciation = context.args[2] if len(context.args) > 2 else None
            
            await self.add_word_complete(update, context, word, definition, pronunciation)
        else:
            # 交互式添加模式
            self.user_states[update.effective_user.id] = {
                'action': 'adding_word', 
                'step': 'word'
            }
            
            keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="cancel_action")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📝 **添加新单词**\n\n请输入要添加的英文单词：",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def add_word_complete(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              word: str, definition: str, pronunciation: str = None):
        """完成添加单词"""
        user_id = update.effective_user.id
        
        if self.db.add_word(user_id, word, definition, pronunciation):
            success_text = f"✅ **单词添加成功！**\n\n"
            success_text += f"📖 **{word}**\n"
            success_text += f"💭 {definition}\n"
            if pronunciation:
                success_text += f"🔊 /{pronunciation}/\n"
            success_text += f"\n💡 将在明天开始复习计划"
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ 继续添加", callback_data="quick_add"),
                    InlineKeyboardButton("📖 开始复习", callback_data="quick_review")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                success_text, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"❌ **添加失败**\n\n单词 `{word}` 可能已存在或格式不正确",
                parse_mode='Markdown'
            )
        
        # 清除用户状态
        self.user_states.pop(user_id, None)
    
    async def list_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """列出单词"""
        user_id = update.effective_user.id
        limit = 10
        
        if context.args:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 50))
            except ValueError:
                await update.message.reply_text("❌ 请输入有效的数字（1-50）")
                return
        
        words = self.db.get_recent_words(user_id, limit)
        
        if not words:
            keyboard = [[InlineKeyboardButton("📝 添加单词", callback_data="quick_add")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📭 **单词库为空**\n\n你还没有添加任何单词。\n点击下方按钮开始添加吧！",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        text_lines = [f"📚 **你的单词库** (最近 {len(words)} 个)\n"]
        
        for i, word in enumerate(words, 1):
            # 状态标识
            if word['review_count'] == 0:
                status = "🆕 新词"
            elif word['mastery_level'] >= 3:
                status = "⭐ 已掌握"
            else:
                status = f"📖 复习{word['review_count']}次"
            
            text_lines.append(f"`{i:2d}.` **{word['word']}**")
            text_lines.append(f"     💭 {word['definition']}")
            text_lines.append(f"     📅 {word['added_date']} | {status}")
            text_lines.append("")
        
        text_lines.append("💡 使用 `/review` 开始复习，`/search` 搜索单词")
        
        keyboard = [
            [
                InlineKeyboardButton("📖 开始复习", callback_data="quick_review"),
                InlineKeyboardButton("🔍 搜索单词", callback_data="quick_search")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            '\n'.join(text_lines), 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def search_words(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """搜索单词"""
        if not context.args:
            self.user_states[update.effective_user.id] = {
                'action': 'searching', 
                'step': 'query'
            }
            
            keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="cancel_action")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔍 **搜索单词**\n\n请输入要搜索的关键词（支持中英文）：",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        query = ' '.join(context.args)
        await self.perform_search(update, context, query)
    
    async def perform_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """执行搜索"""
        user_id = update.effective_user.id
        results = self.db.search_words(user_id, query, 20)
        
        if not results:
            await update.message.reply_text(
                f"🔍 **搜索结果**\n\n没有找到包含 `{query}` 的单词\n\n💡 试试其他关键词或添加新单词",
                parse_mode='Markdown'
            )
            return
        
        text_lines = [f"🔍 **搜索结果** (找到 {len(results)} 个)\n"]
        text_lines.append(f"关键词: `{query}`\n")
        
        for i, word in enumerate(results[:10], 1):  # 显示前10个
            # 高亮匹配的关键词
            highlighted_word = word['word']
            highlighted_def = word['definition']
            
            text_lines.append(f"`{i:2d}.` **{highlighted_word}**")
            text_lines.append(f"     💭 {highlighted_def}")
            
            # 显示复习信息
            if word['review_count'] == 0:
                text_lines.append(f"     🆕 新词")
            else:
                next_review = word['next_review_date']
                text_lines.append(f"     📖 复习{word['review_count']}次 | 下次: {next_review}")
            
            text_lines.append("")
        
        if len(results) > 10:
            text_lines.append(f"... 还有 {len(results) - 10} 个结果")
        
        await update.message.reply_text('\n'.join(text_lines), parse_mode='Markdown')
        
        # 清除搜索状态
        self.user_states.pop(user_id, None)
    
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
            keyboard = [
                [InlineKeyboardButton("📝 添加单词", callback_data="quick_add")],
                [InlineKeyboardButton("📊 查看统计", callback_data="quick_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎉 **太棒了！**\n\n今天没有需要复习的单词。\n\n你可以：\n• 添加新单词扩展词汇量\n• 查看学习统计了解进度",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
        
        # 设置复习状态
        self.user_states[user_id] = {
            'action': 'reviewing',
            'words': words,
            'current_index': 0,
            'correct_count': 0,
            'start_time': datetime.now()
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
            await self.finish_review(update, context)
            return
        
        word_data = words[current_index]
        progress = f"({current_index + 1}/{len(words)})"
        
        # 构建单词信息
        word_text = f"📖 **复习单词** {progress}\n\n"
        word_text += f"🔤 **{word_data['word'].upper()}**\n\n"
        
        if word_data.get('pronunciation'):
            word_text += f"🔊 /{word_data['pronunciation']}/\n\n"
        
        word_text += "你还记得这个单词的意思吗？"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ 记得很清楚", callback_data=f"review_perfect_{word_data['id']}"),
                InlineKeyboardButton("🤔 有点印象", callback_data=f"review_partial_{word_data['id']}")
            ],
            [
                InlineKeyboardButton("❌ 完全忘了", callback_data=f"review_forgot_{word_data['id']}"),
                InlineKeyboardButton("👀 查看答案", callback_data=f"review_show_{word_data['id']}")
            ],
            [
                InlineKeyboardButton("⏸️ 暂停复习", callback_data="pause_review")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                word_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                word_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
    
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
        if len(action_parts) < 3:
            return
            
        action = action_parts[1]  # perfect, partial, forgot, show
        word_id = int(action_parts[2])
        
        words = state['words']
        current_index = state['current_index']
        
        if current_index >= len(words):
            return
            
        word_data = words[current_index]
        
        if action == 'show':
            # 显示释义
            answer_text = f"📖 **单词释义**\n\n"
            answer_text += f"🔤 **{word_data['word'].upper()}**\n\n"
            
            if word_data.get('pronunciation'):
                answer_text += f"🔊 /{word_data['pronunciation']}/\n\n"
            
            answer_text += f"💭 **{word_data['definition']}**\n\n"
            
            if word_data.get('example_sentence'):
                answer_text += f"📝 例句: {word_data['example_sentence']}\n\n"
            
            answer_text += "现在你记起来了吗？"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ 记住了", callback_data=f"review_partial_{word_id}"),
                    InlineKeyboardButton("❌ 还是忘了", callback_data=f"review_forgot_{word_id}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                answer_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
            
        elif action in ['perfect', 'partial', 'forgot']:
            # 处理复习结果
            mastered_map = {
                'perfect': True,
                'partial': True,
                'forgot': False
            }
            
            difficulty_map = {
                'perfect': 1,  # 简单
                'partial': 3,  # 中等
                'forgot': 5    # 困难
            }
            
            mastered = mastered_map[action]
            difficulty = difficulty_map[action]
            
            self.db.update_word_review(word_id, mastered, difficulty)
            
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
        start_time = state.get('start_time', datetime.now())
        
        duration = (datetime.now() - start_time).total_seconds()
        accuracy = (correct_count / total_words * 100) if total_words > 0 else 0
        
        # 记录复习会话
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO review_sessions 
            (user_id, words_reviewed, correct_answers, session_duration_seconds)
            VALUES (?, ?, ?, ?)
        ''', (user_id, total_words, correct_count, int(duration)))
        conn.commit()
        conn.close()
        
        # 清除状态
        self.user_states.pop(user_id, None)
        
        # 生成表现评价
        if accuracy >= 90:
            performance = "🏆 完美表现！"
        elif accuracy >= 70:
            performance = "👍 表现不错！"
        elif accuracy >= 50:
            performance = "💪 继续努力！"
        else:
            performance = "📚 需要加强复习"
        
        result_text = f"🎉 **复习完成！** {performance}\n\n"
        result_text += f"📊 **本次复习统计**\n"
        result_text += f"• 复习单词: {total_words} 个\n"
        result_text += f"• 掌握单词: {correct_count} 个\n"
        result_text += f"• 准确率: {accuracy:.1f}%\n"
        result_text += f"• 用时: {int(duration//60)}分{int(duration%60)}秒\n\n"
        result_text += f"💡 **记忆提醒**\n"
        result_text += f"• 掌握的单词会延长复习间隔\n"
        result_text += f"• 遗忘的单词会增加复习频率\n"
        result_text += f"• 坚持复习是掌握词汇的关键！\n\n"
        result_text += f"继续加油！🚀"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 查看统计", callback_data="quick_stats"),
                InlineKeyboardButton("🔄 再次复习", callback_data="quick_review")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                result_text, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                result_text, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """显示学习统计"""
        user_id = update.effective_user.id
        stats = self.db.get_user_stats(user_id)
        
        # 构建统计信息
        stats_text = f"📊 **你的学习数据分析**\n\n"
        
        # 词汇库状态
        stats_text += f"📚 **词汇库状态**\n"
        stats_text += f"• 总单词数: {stats['total_words']} 个\n"
        stats_text += f"• 新单词: {stats['new_words']} 个\n"
        stats_text += f"• 待复习: {stats['due_words']} 个\n"
        stats_text += f"• 已掌握: {stats['mastered_words']} 个\n\n"
        
        # 今日学习情况
        stats_text += f"📈 **今日学习**\n"
        stats_text += f"• 复习单词: {stats['today_reviewed']} 个\n"
        stats_text += f"• 答对单词: {stats['today_correct']} 个\n"
        if stats['today_reviewed'] > 0:
            today_accuracy = (stats['today_correct'] / stats['today_reviewed'] * 100)
            stats_text += f"• 今日准确率: {today_accuracy:.1f}%\n"
        stats_text += f"\n"
        
        # 学习成就
        stats_text += f"🏆 **学习成就**\n"
        stats_text += f"• 掌握率: {stats['mastery_rate']:.1f}%\n"
        stats_text += f"• 学习天数: {stats['learning_streak']} 天\n\n"
        
        # 学习建议
        stats_text += f"💡 **学习建议**\n"
        if stats['due_words'] > 0:
            stats_text += f"• 有 {stats['due_words']} 个单词需要复习\n"
            stats_text += f"• 建议现在开始复习保持记忆新鲜度\n"
        elif stats['new_words'] > 0:
            stats_text += f"• 有 {stats['new_words']} 个新单词等待学习\n"
            stats_text += f"• 建议开始学习新词汇扩展词汇量\n"
        else:
            stats_text += f"• 今天的学习任务完成了！\n"
            stats_text += f"• 可以休息一下或添加新单词\n"
        
        keyboard = [
            [
                InlineKeyboardButton("📖 开始复习", callback_data="quick_review"),
                InlineKeyboardButton("📝 添加单词", callback_data="quick_add")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            stats_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询"""
        query = update.callback_query
        
        if query.data.startswith('review_'):
            await self.handle_review_callback(update, context)
            return
        
        await query.answer()
        
        # 快速操作
        if query.data == 'quick_add':
            self.user_states[update.effective_user.id] = {
                'action': 'adding_word', 
                'step': 'word'
            }
            
            keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="cancel_action")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📝 **添加新单词**\n\n请输入要添加的英文单词：",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        elif query.data == 'quick_review':
            await self.start_review(update, context)
            
        elif query.data == 'quick_stats':
            await self.show_stats(update, context)
            
        elif query.data == 'quick_help':
            await self.help_command(update, context)
            
        elif query.data == 'cancel_action':
            user_id = update.effective_user.id
            self.user_states.pop(user_id, None)
            
            await query.edit_message_text(
                "❌ **操作已取消**\n\n使用命令重新开始操作",
                parse_mode='Markdown'
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理普通消息"""
        user_id = update.effective_user.id
        state = self.user_states.get(user_id, {})
        message_text = update.message.text.strip()
        
        if state.get('action') == 'adding_word':
            if state.get('step') == 'word':
                # 获取单词
                if not message_text or ' ' in message_text or not message_text.replace('-', '').isalpha():
                    await update.message.reply_text(
                        "❌ **格式错误**\n\n请输入一个有效的英文单词（只能包含字母和连字符）"
                    )
                    return
                
                state['word'] = message_text.lower()
                state['step'] = 'definition'
                self.user_states[user_id] = state
                
                await update.message.reply_text(
                    f"📖 **单词**: `{message_text}`\n\n💭 请输入中文释义：",
                    parse_mode='Markdown'
                )
                
            elif state.get('step') == 'definition':
                if not message_text:
                    await update.message.reply_text("❌ 请输入有效的释义")
                    return
                
                word = state['word']
                await self.add_word_complete(update, context, word, message_text)
                
        elif state.get('action') == 'searching':
            if state.get('step') == 'query':
                if not message_text:
                    await update.message.reply_text("❌ 请输入有效的搜索关键词")
                    return
                
                await self.perform_search(update, context, message_text)
                
        else:
            # 智能识别用户意图
            text_lower = message_text.lower()
            
            if any(word in text_lower for word in ['add', '添加', 'new', '新']):
                await update.message.reply_text(
                    "💡 **想要添加单词？**\n\n使用命令：`/add 单词 释义`\n或发送 `/add` 进入交互模式",
                    parse_mode='Markdown'
                )
            elif any(word in text_lower for word in ['review', '复习', 'study', '学习']):
                await update.message.reply_text(
                    "💡 **想要开始复习？**\n\n使用命令：`/review`",
                    parse_mode='Markdown'
                )
            elif any(word in text_lower for word in ['search', '搜索', 'find', '查找']):
                await update.message.reply_text(
                    "💡 **想要搜索单词？**\n\n使用命令：`/search 关键词`",
                    parse_mode='Markdown'
                )
            else:
                # 提供帮助
                keyboard = [
                    [
                        InlineKeyboardButton("📝 添加单词", callback_data="quick_add"),
                        InlineKeyboardButton("📖 开始复习", callback_data="quick_review")
                    ],
                    [
                        InlineKeyboardButton("🔍 搜索单词", callback_data="quick_search"),
                        InlineKeyboardButton("❓ 查看帮助", callback_data="quick_help")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "🤖 **我没有理解你的意思**\n\n请选择下面的操作或使用 `/help` 查看所有命令：",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
    
    async def export_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """导出数据"""
        user_id = update.effective_user.id
        
        # 获取用户所有单词
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT word, definition, pronunciation, added_date, 
                   last_reviewed_date, review_count, mastery_level
            FROM words 
            WHERE user_id = ?
            ORDER BY added_date DESC
        ''', (user_id,))
        
        words = cursor.fetchall()
        conn.close()
        
        if not words:
            await update.message.reply_text("📭 没有数据可导出")
            return
        
        # 生成JSON格式数据
        export_data = {
            'export_date': datetime.now().isoformat(),
            'user_id': user_id,
            'total_words': len(words),
            'words': [dict(word) for word in words]
        }
        
        # 创建临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            temp_path = f.name
        
        try:
            # 发送文件
            await update.message.reply_document(
                document=open(temp_path, 'rb'),
                filename=f"gre_words_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                caption=f"📦 **数据导出完成**\n\n• 总单词数: {len(words)}\n• 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode='Markdown'
            )
        finally:
            # 清理临时文件
            os.unlink(temp_path)
    
    async def set_bot_commands(self):
        """设置Bot命令菜单"""
        commands = [
            BotCommand("start", "🚀 开始使用"),
            BotCommand("add", "📝 添加单词"),
            BotCommand("review", "📖 开始复习"),
            BotCommand("list", "📋 浏览单词库"),
            BotCommand("search", "🔍 搜索单词"),
            BotCommand("stats", "📊 学习统计"),
            BotCommand("export", "📦 导出数据"),
            BotCommand("settings", "⚙️ 个人设置"),
            BotCommand("help", "❓ 帮助指南"),
        ]
        
        app = Application.builder().token(self.bot_token).build()
        await app.bot.set_my_commands(commands)
        logger.info("Bot命令菜单设置完成")
    
    def run(self):
        """运行Bot"""
        try:
            # 创建Application
            application = Application.builder().token(self.bot_token).build()
            
            # 添加处理器
            application.add_handler(CommandHandler("start", self.start))
            application.add_handler(CommandHandler("help", self.help_command))
            application.add_handler(CommandHandler("add", self.add_word_command))
            application.add_handler(CommandHandler("list", self.list_words))
            application.add_handler(CommandHandler("search", self.search_words))
            application.add_handler(CommandHandler("review", self.start_review))
            application.add_handler(CommandHandler("stats", self.show_stats))
            application.add_handler(CommandHandler("export", self.export_data))
            
            # 回调查询处理器
            application.add_handler(CallbackQueryHandler(self.handle_callback_query))
            
            # 消息处理器
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                self.handle_message
            ))
            
            # 设置Bot命令（异步）
            async def setup():
                await self.set_bot_commands()
            
            # 运行设置
            asyncio.create_task(setup())
            
            logger.info("🤖 GRE Telegram Bot 启动成功")
            print("🤖 GRE Telegram Bot 正在运行...")
            print("按 Ctrl+C 停止")
            
            # 启动Bot
            application.run_polling()
            
        except Exception as e:
            logger.error(f"Bot运行失败: {e}")
            raise

if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    project_root = Path(__file__).parent
    bot = GREBot(project_root)
    bot.run()
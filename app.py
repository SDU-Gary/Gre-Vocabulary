#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE单词添加Web应用
修复版：添加身份验证，增强错误处理，使用安全文件操作
"""

from flask import Flask, request, render_template, redirect, url_for, flash, session
import csv
import os
import hashlib
from datetime import date, datetime
from functools import wraps
from safe_csv import get_csv_handler

app = Flask(__name__)

# --- 配置区 ---
# 请务必修改这些配置！
APP_SECRET_KEY = os.getenv('GRE_SECRET_KEY', 'change-me-to-a-random-secret-key-123')
APP_PASSWORD = os.getenv('GRE_PASSWORD', 'gre2024')  # 默认密码，建议通过环境变量设置
CSV_FILE_PATH = os.getenv('GRE_CSV_PATH', '/home/your_user/gre_word_pusher/words.csv')

app.secret_key = APP_SECRET_KEY

# 简单的密码哈希（用于session验证）
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

PASSWORD_HASH = hash_password(APP_PASSWORD)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('请先登录')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        
        if hash_password(password) == PASSWORD_HASH:
            session['logged_in'] = True
            session['login_time'] = datetime.now().isoformat()
            flash('登录成功！')
            return redirect(url_for('index'))
        else:
            flash('密码错误，请重试')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """登出"""
    session.clear()
    flash('已安全登出')
    return redirect(url_for('login'))


def add_word_to_csv(word, definition):
    """
    向 CSV 文件安全追加一个新单词
    使用安全的文件操作避免并发问题
    """
    try:
        today_str = date.today().isoformat()
        # 新单词格式: word,definition,added_date,last_reviewed_date,review_count
        # last_reviewed_date 初始化为添加日期，review_count 为 0
        new_row = [word.strip(), definition.strip(), today_str, today_str, '0']
        
        csv_handler = get_csv_handler(CSV_FILE_PATH)
        return csv_handler.append_word(new_row)
    except Exception as e:
        print(f"添加单词到CSV文件失败: {e}")
        return False


def word_exists_safe(word):
    """
    安全检查单词是否存在
    使用优化的检查方法，避免读取整个文件
    """
    try:
        csv_handler = get_csv_handler(CSV_FILE_PATH)
        return csv_handler.word_exists(word)
    except Exception as e:
        print(f"检查单词存在性失败: {e}")
        return False


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """主页 - 添加单词"""
    if request.method == 'POST':
        word = request.form.get('word', '').strip()
        definition = request.form.get('definition', '').strip()
        
        # 输入验证
        if not word or not definition:
            flash('单词和释义均不能为空')
            return redirect(url_for('index'))
        
        if len(word) > 50 or len(definition) > 200:
            flash('单词或释义过长，请检查输入')
            return redirect(url_for('index'))
        
        # 检查重复
        try:
            if word_exists_safe(word):
                flash(f"单词 '{word}' 已存在！")
                return redirect(url_for('index'))
        except Exception as e:
            flash(f'检查单词时出错: {str(e)}')
            return redirect(url_for('index'))
        
        # 添加单词
        success = False
        try:
            if add_word_to_csv(word, definition):
                flash(f"✅ 成功添加单词: {word}")
                success = True
            else:
                flash('❌ 添加失败，请重试或联系管理员')
        except Exception as e:
            flash(f'添加单词时出错: {str(e)}')
        
        # 使用更稳定的重定向，添加小延迟以确保扩展脚本完成
        import time
        time.sleep(0.1)  # 100ms延迟
        
        # 如果成功添加，在URL中添加成功标识
        redirect_url = url_for('index') + ('#success' if success else '')
        response = redirect(redirect_url)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache' 
        response.headers['Expires'] = '0'
        return response

    return render_template('index.html')


@app.route('/stats')
@login_required 
def stats():
    """简单的统计页面"""
    try:
        csv_handler = get_csv_handler(CSV_FILE_PATH)
        all_words = csv_handler.read_all_words()
        
        if not all_words:
            return render_template('stats.html', 
                                 total=0, new_words=0, reviewed=0, 
                                 avg_reviews=0, recent_words=[])
        
        total_words = len(all_words)
        new_words = sum(1 for row in all_words if len(row) >= 5 and row[4] == '0')
        reviewed_words = total_words - new_words
        
        # 计算平均复习次数
        total_reviews = sum(int(row[4]) for row in all_words if len(row) >= 5 and row[4].isdigit())
        avg_reviews = round(total_reviews / max(total_words, 1), 1)
        
        # 最近添加的5个单词
        recent_words = []
        for row in all_words[-5:]:
            if len(row) >= 3:
                recent_words.append({'word': row[0], 'definition': row[1], 'date': row[2]})
        recent_words.reverse()  # 最新的在前面
        
        return render_template('stats.html',
                             total=total_words, 
                             new_words=new_words,
                             reviewed=reviewed_words,
                             avg_reviews=avg_reviews,
                             recent_words=recent_words)
    
    except Exception as e:
        flash(f'获取统计信息失败: {str(e)}')
        return render_template('stats.html', 
                             total=0, new_words=0, reviewed=0, 
                             avg_reviews=0, recent_words=[])


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_code=404, 
                         error_msg='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', 
                         error_code=500, 
                         error_msg='服务器内部错误'), 500


if __name__ == '__main__':
    # 这个仅用于本地测试，生产环境请使用 Gunicorn
    print("🚀 GRE单词管理系统启动中...")
    print(f"📁 数据文件路径: {CSV_FILE_PATH}")
    print(f"🔐 默认密码: {APP_PASSWORD} (请通过环境变量 GRE_PASSWORD 修改)")
    app.run(host='0.0.0.0', port=5000, debug=False)  # 生产环境关闭debug
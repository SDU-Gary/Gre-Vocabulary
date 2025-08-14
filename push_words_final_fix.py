#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE单词推送脚本 - 最终修复版本
解决ntfy.sh中文编码问题的终极方案
"""

import csv
import requests
import random
import time
import json
from datetime import date, timedelta, datetime
from safe_csv import get_csv_handler

# --- 配置区 ---
NTFY_TOPIC = "gre-words-for-my-awesome-life-123xyz"
CSV_FILE_PATH = "/root/gre_word_pusher/words.csv"
WORDS_PER_PUSH = 15

# --- 艾宾浩斯记忆曲线间隔 (天) ---
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30, 60]


def load_config():
    """从环境变量文件加载配置"""
    global NTFY_TOPIC, CSV_FILE_PATH, WORDS_PER_PUSH
    
    try:
        import os
        # 尝试从环境变量读取
        NTFY_TOPIC = os.getenv('NTFY_TOPIC', NTFY_TOPIC)
        CSV_FILE_PATH = os.getenv('GRE_CSV_PATH', CSV_FILE_PATH)
        
        # 尝试从.env文件读取
        env_file = '/root/gre_word_pusher/.env'
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NTFY_TOPIC='):
                        NTFY_TOPIC = line.split('=', 1)[1].strip()
                    elif line.startswith('GRE_CSV_PATH='):
                        CSV_FILE_PATH = line.split('=', 1)[1].strip()
                    elif line.startswith('WORDS_PER_PUSH='):
                        try:
                            WORDS_PER_PUSH = int(line.split('=', 1)[1].strip())
                        except ValueError:
                            pass
        
        print(f"📋 配置加载完成:")
        print(f"   NTFY主题: {NTFY_TOPIC}")
        print(f"   CSV路径: {CSV_FILE_PATH}")
        print(f"   推送数量: {WORDS_PER_PUSH}")
        
    except Exception as e:
        print(f"⚠️ 配置加载失败，使用默认值: {e}")


def get_review_words(file_path, num_words):
    """
    基于艾宾浩斯记忆曲线挑选单词。
    优先级: 1. 新词 (review_count=0)  2. 到达复习日期的词
    使用安全的文件操作
    """
    csv_handler = get_csv_handler(file_path)
    all_words = csv_handler.read_all_words()
    
    if not all_words:
        print("📁 CSV文件为空或不存在")
        return [], [], set()

    today = date.today()
    due_words = []
    
    # 1. 筛选出所有新词和到期的词
    for i, row in enumerate(all_words):
        try:
            if len(row) < 5:
                print(f"⚠️ 跳过格式不完整的行 {i+1}: {row}")
                continue
                
            word, definition, added_date, last_reviewed_date, review_count_str = row
            review_count = int(review_count_str)
            
            # 优先处理新词 
            if review_count == 0:
                due_words.append((row, -999, i))  # 用-999保证新词排序最前
                continue

            # 计算下一次复习日期
            try:
                last_review_dt = datetime.strptime(last_reviewed_date, '%Y-%m-%d').date()
            except ValueError:
                print(f"⚠️ 跳过日期格式错误的行 {i+1}: {row}")
                continue
                
            # 获取当前阶段对应的间隔天数
            interval_days = REVIEW_INTERVALS[min(review_count, len(REVIEW_INTERVALS) - 1)]
            next_review_date = last_review_dt + timedelta(days=interval_days)

            if today >= next_review_date:
                days_overdue = (today - next_review_date).days
                due_words.append((row, days_overdue, i))  # 记录原始索引
                
        except (ValueError, IndexError) as e:
            print(f"⚠️ 跳过格式错误的行 {i+1}: {row}. 错误: {e}")
            continue

    # 2. 排序：最逾期的 > 新词 > 刚到期的
    due_words.sort(key=lambda x: x[1], reverse=True)
    
    # 3. 提取要复习的单词列表和它们的原始索引
    words_to_review_with_indices = due_words[:num_words]
    words_to_review = [item[0] for item in words_to_review_with_indices]
    original_indices = {item[2] for item in words_to_review_with_indices}

    return words_to_review, all_words, original_indices


def send_notification_simple_json(topic, words_to_review, max_retries=3):
    """
    使用简化的JSON格式推送（适配ntfy.sh API要求）
    """
    if not words_to_review:
        print("📭 没有需要复习的单词。")
        return False

    # 构建消息内容
    message_lines = []
    for i, word_data in enumerate(words_to_review, 1):
        if len(word_data) >= 2:
            word, definition = word_data[0], word_data[1]
            message_lines.append(f"{i}. {word}: {definition}")
    
    if not message_lines:
        print("❌ 没有有效的单词数据")
        return False
        
    message = "\n".join(message_lines)
    message += f"\n\n📚 共{len(words_to_review)}个单词"
    message += "\n💡 艾宾浩斯记忆曲线推送"
    
    for attempt in range(max_retries):
        try:
            # 方法1: 使用正确的JSON格式
            payload = {
                "topic": topic,
                "message": message,
                "title": f"🧠 GRE单词复习 ({len(words_to_review)}词)"
            }
            
            response = requests.post(
                "https://ntfy.sh/",
                data=json.dumps(payload),
                headers={
                    "Content-Type": "application/json"
                },
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"✅ 成功发送 {len(words_to_review)} 个单词到 ntfy (简化JSON)")
                return True
            else:
                print(f"❌ 简化JSON推送失败: {response.status_code}")
                print(f"响应: {response.text}")
                
        except Exception as e:
            print(f"❌ 简化JSON推送异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    return False


def send_notification_encoded_post(topic, words_to_review, max_retries=3):
    """
    使用编码后的POST方法推送
    """
    if not words_to_review:
        return False

    # 构建消息内容
    message_lines = []
    for i, word_data in enumerate(words_to_review, 1):
        if len(word_data) >= 2:
            word, definition = word_data[0], word_data[1]
            message_lines.append(f"{i}. {word}: {definition}")
    
    if not message_lines:
        return False
        
    message = "\n".join(message_lines)
    message += f"\n\n📚 共{len(words_to_review)}个单词"
    
    for attempt in range(max_retries):
        try:
            # 直接发送UTF-8编码的字节数据
            response = requests.post(
                f"https://ntfy.sh/{topic}",
                data=message.encode('utf-8'),
                headers={
                    "Title": f"GRE单词复习 ({len(words_to_review)}词)".encode('utf-8').decode('latin-1'),
                    "Priority": "default"
                },
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"✅ 成功发送 {len(words_to_review)} 个单词到 ntfy (编码POST)")
                return True
            else:
                print(f"❌ 编码POST推送失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 编码POST推送异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    return False


def send_notification_english_fallback(topic, words_to_review, max_retries=3):
    """
    英文降级推送方案
    """
    if not words_to_review:
        return False

    # 创建英文格式消息
    message_lines = []
    for i, word_data in enumerate(words_to_review, 1):
        if len(word_data) >= 2:
            word, definition = word_data[0], word_data[1]
            # 只保留英文单词，避免中文编码问题
            message_lines.append(f"{i}. {word}")
    
    if not message_lines:
        return False
        
    message = f"GRE Words Review ({len(words_to_review)} words):\n\n"
    message += "\n".join(message_lines)
    message += "\n\nCheck your study app for Chinese definitions."
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"https://ntfy.sh/{topic}",
                data=message,
                headers={
                    "Title": f"GRE Review - {len(words_to_review)} words",
                    "Priority": "high",
                    "Tags": "brain,study,gre"
                },
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"✅ 成功发送 {len(words_to_review)} 个单词到 ntfy (英文格式)")
                return True
            else:
                print(f"❌ 英文推送失败: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 英文推送异常 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    return False


def send_notification_with_retry(topic, words_to_review, max_retries=3):
    """
    智能推送：尝试多种方法，确保推送成功
    """
    if not words_to_review:
        print("📭 没有需要复习的单词。")
        return False
        
    print(f"📱 开始推送 {len(words_to_review)} 个单词...")
    
    # 方法1: 尝试简化JSON格式推送
    print("🔄 尝试简化JSON格式推送...")
    if send_notification_simple_json(topic, words_to_review, 2):
        return True
    
    # 方法2: 尝试编码POST推送
    print("🔄 JSON失败，尝试编码POST推送...")
    if send_notification_encoded_post(topic, words_to_review, 2):
        return True
    
    # 方法3: 降级到英文格式推送
    print("🔄 编码POST失败，降级到英文推送...")
    if send_notification_english_fallback(topic, words_to_review, 2):
        return True
    
    # 方法4: 记录失败日志
    print("❌ 所有推送方法都失败了")
    log_failed_notification(words_to_review)
    return False


def update_and_save_words(file_path, all_words, reviewed_indices):
    """
    更新复习过的单词的状态并安全写回文件
    使用备份机制防止数据损坏
    """
    if not reviewed_indices:
        return
        
    today_str = date.today().isoformat()
    updated_count = 0
    
    for i, row in enumerate(all_words):
        if i in reviewed_indices and len(row) >= 5:
            row[3] = today_str  # 更新上次复习日期
            row[4] = str(int(row[4]) + 1)  # 记忆阶段+1
            updated_count += 1
    
    csv_handler = get_csv_handler(file_path)
    try:
        csv_handler.write_all_words(all_words, create_backup=True)
        print(f"✅ 成功更新 {updated_count} 个单词的复习状态")
    except Exception as e:
        print(f"❌ 更新单词状态失败: {e}")


def log_failed_notification(words_to_review):
    """记录推送失败的单词，供后续重试"""
    try:
        timestamp = datetime.now().isoformat()
        failed_log_path = CSV_FILE_PATH.replace('.csv', '_failed_notifications.log')
        
        with open(failed_log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n--- {timestamp} ---\n")
            for word_data in words_to_review:
                if len(word_data) >= 2:
                    f.write(f"{word_data[0]}: {word_data[1]}\n")
            f.write("--- End ---\n")
        
        print(f"📝 失败的推送已记录到: {failed_log_path}")
    except Exception as e:
        print(f"❌ 记录失败日志时出错: {e}")


if __name__ == "__main__":
    print("="*50)
    print("🚀 GRE单词推送系统启动 - 最终修复版")
    print(f"⏰ 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    try:
        # 1. 加载配置
        load_config()
        
        # 2. 获取需要复习的单词
        print("\n📚 分析需要复习的单词...")
        review_list, all_data, reviewed_idx = get_review_words(CSV_FILE_PATH, WORDS_PER_PUSH)
        
        if review_list:
            print(f"📋 找到 {len(review_list)} 个需要复习的单词:")
            for i, word_data in enumerate(review_list[:5], 1):  # 显示前5个
                if len(word_data) >= 2:
                    print(f"   {i}. {word_data[0]}: {word_data[1]}")
            if len(review_list) > 5:
                print(f"   ... 还有 {len(review_list)-5} 个单词")
            
            # 3. 发送推送
            success = send_notification_with_retry(NTFY_TOPIC, review_list)
            
            # 4. 更新复习状态
            if success:
                update_and_save_words(CSV_FILE_PATH, all_data, reviewed_idx)
                print("✅ 推送成功，单词状态已更新")
            else:
                print("❌ 由于推送失败，未更新单词状态")
        else:
            print("📭 今天没有需要复习的单词")
            
    except Exception as e:
        print(f"❌ 脚本执行出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    print(f"🏁 任务完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE单词推送脚本 - 基于艾宾浩斯记忆曲线
修复版：解决并发问题，增强错误处理
"""

import csv
import requests
import random
import time
from datetime import date, timedelta, datetime
from safe_csv import get_csv_handler

# --- 配置区 ---
NTFY_TOPIC = "gre-words-for-my-awesome-life-123xyz"  # 换成你的 ntfy 主题
CSV_FILE_PATH = "/home/your_user/gre_word_pusher/words.csv"
WORDS_PER_PUSH = 15

# --- 艾宾浩斯记忆曲线间隔 (天) ---
# 分别是：新词(0), 复习1次后, 复习2次后, ...
# 第0阶段(新词)实际上是立即复习，这里用1天作为首次复习间隔
REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30, 60]


def get_review_words(file_path, num_words):
    """
    基于艾宾浩斯记忆曲线挑选单词。
    优先级: 1. 新词 (review_count=0)  2. 到达复习日期的词
    使用安全的文件操作
    """
    csv_handler = get_csv_handler(file_path)
    all_words = csv_handler.read_all_words()
    
    if not all_words:
        print("CSV文件为空或不存在")
        return [], [], set()

    today = date.today()
    due_words = []
    
    # 1. 筛选出所有新词和到期的词
    for i, row in enumerate(all_words):
        try:
            if len(row) < 5:
                print(f"警告: 跳过格式不完整的行 {i+1}: {row}")
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
                print(f"警告: 跳过日期格式错误的行 {i+1}: {row}")
                continue
                
            # 获取当前阶段对应的间隔天数，如果超出预设则使用最后一个间隔
            interval_days = REVIEW_INTERVALS[min(review_count, len(REVIEW_INTERVALS) - 1)]
            next_review_date = last_review_dt + timedelta(days=interval_days)

            if today >= next_review_date:
                days_overdue = (today - next_review_date).days
                due_words.append((row, days_overdue, i))  # 记录原始索引
                
        except (ValueError, IndexError) as e:
            print(f"警告: 跳过格式错误的行 {i+1}: {row}. 错误: {e}")
            continue

    # 2. 排序：最逾期的 > 新词 > 刚到期的
    due_words.sort(key=lambda x: x[1], reverse=True)
    
    # 3. 提取要复习的单词列表和它们的原始索引
    words_to_review_with_indices = due_words[:num_words]
    words_to_review = [item[0] for item in words_to_review_with_indices]
    original_indices = {item[2] for item in words_to_review_with_indices}

    return words_to_review, all_words, original_indices


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
        print(f"成功更新 {updated_count} 个单词的复习状态")
    except Exception as e:
        print(f"更新单词状态失败: {e}")


def send_notification_with_retry(topic, words_to_review, max_retries=3):
    """
    发送推送通知，带重试机制
    """
    if not words_to_review:
        print("没有需要复习的单词。")
        return False

    message_lines = []
    for word_data in words_to_review:
        if len(word_data) >= 2:
            word, definition = word_data[0], word_data[1]
            message_lines.append(f"{word}: {definition}")
    
    if not message_lines:
        print("没有有效的单词数据")
        return False
        
    message = "\n".join(message_lines)
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"https://ntfy.sh/{topic}",
                data=message.encode('utf-8'),
                headers={
                    "Title": f"GRE 单词复习！({len(words_to_review)}词)",
                    "Priority": "high",
                    "Tags": "brain,study",
                    "Content-Type": "text/plain; charset=utf-8"
                },
                timeout=10  # 10秒超时
            )
            
            if response.status_code == 200:
                print(f"成功发送 {len(words_to_review)} 个单词到 ntfy 主题: {topic}")
                return True
            else:
                print(f"ntfy 返回错误状态码: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"发送 ntfy 推送失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                
        except Exception as e:
            print(f"未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    print(f"推送失败，已重试 {max_retries} 次")
    # 写入失败日志，供后续处理
    log_failed_notification(words_to_review)
    return False


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
        
        print(f"失败的推送已记录到: {failed_log_path}")
    except Exception as e:
        print(f"记录失败日志时出错: {e}")


if __name__ == "__main__":
    print(f"开始执行单词推送任务 - {datetime.now()}")
    
    try:
        review_list, all_data, reviewed_idx = get_review_words(CSV_FILE_PATH, WORDS_PER_PUSH)
        
        if review_list:
            print(f"找到 {len(review_list)} 个需要复习的单词")
            success = send_notification_with_retry(NTFY_TOPIC, review_list)
            
            if success:
                update_and_save_words(CSV_FILE_PATH, all_data, reviewed_idx)
            else:
                print("由于推送失败，未更新单词状态")
        else:
            print("今天没有需要复习的单词")
            
    except Exception as e:
        print(f"脚本执行出错: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"任务完成 - {datetime.now()}")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复推送编码问题的临时脚本
"""

import requests
import json
from datetime import datetime

def test_push_methods(topic, words_data):
    """测试不同的推送方法"""
    
    # 准备测试消息
    test_message = "测试中文: ubiquitous(普遍存在的)"
    
    print("🧪 测试不同的推送方法...")
    
    # 方法1: JSON格式推送
    print("\n1️⃣ 尝试JSON格式推送...")
    try:
        payload = {
            "topic": topic,
            "message": test_message,
            "title": "GRE单词推送测试",
            "priority": "default",
            "tags": ["brain", "study"]
        }
        
        response = requests.post(
            "https://ntfy.sh/",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ JSON格式推送成功！")
            return "json"
        else:
            print(f"❌ JSON推送失败: {response.status_code}")
            print(f"响应: {response.text}")
    
    except Exception as e:
        print(f"❌ JSON推送异常: {e}")
    
    # 方法2: URL编码推送
    print("\n2️⃣ 尝试URL编码推送...")
    try:
        import urllib.parse
        
        params = {
            "title": "GRE单词推送测试",
            "priority": "default",
            "tags": "brain,study"
        }
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=test_message.encode('utf-8'),
            params=params,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ URL编码推送成功！")
            return "url_encoded"
        else:
            print(f"❌ URL编码推送失败: {response.status_code}")
            print(f"响应: {response.text}")
    
    except Exception as e:
        print(f"❌ URL编码推送异常: {e}")
    
    # 方法3: 纯英文推送测试
    print("\n3️⃣ 尝试纯英文推送...")
    try:
        english_message = "Test: ubiquitous (everywhere, common)"
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=english_message,
            headers={
                "Title": "GRE Words Review",
                "Priority": "high",
                "Tags": "brain,study"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ 纯英文推送成功！")
            return "english_only"
        else:
            print(f"❌ 纯英文推送失败: {response.status_code}")
    
    except Exception as e:
        print(f"❌ 纯英文推送异常: {e}")
    
    print("\n❌ 所有推送方法都失败了")
    return None

def create_fixed_push_function(method):
    """根据测试结果创建修复的推送函数"""
    
    if method == "json":
        return '''
def send_notification_with_retry(topic, words_to_review, max_retries=3):
    """发送推送通知 - JSON方法"""
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
        
    message = "\\n".join(message_lines)
    
    for attempt in range(max_retries):
        try:
            payload = {
                "topic": topic,
                "message": message,
                "title": f"GRE 单词复习！({len(words_to_review)}词)",
                "priority": "default",
                "tags": ["brain", "study"]
            }
            
            response = requests.post(
                "https://ntfy.sh/",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"成功发送 {len(words_to_review)} 个单词到 ntfy 主题: {topic}")
                return True
            else:
                print(f"ntfy 返回错误状态码: {response.status_code}")
                
        except Exception as e:
            print(f"推送失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    print(f"推送失败，已重试 {max_retries} 次")
    log_failed_notification(words_to_review)
    return False
'''
    
    elif method == "english_only":
        return '''
def send_notification_with_retry(topic, words_to_review, max_retries=3):
    """发送推送通知 - 纯英文方法"""
    if not words_to_review:
        print("没有需要复习的单词。")
        return False

    message_lines = []
    for word_data in words_to_review:
        if len(word_data) >= 2:
            word, definition = word_data[0], word_data[1]
            # 转换为英文格式，避免中文编码问题
            message_lines.append(f"{word} - {definition}")
    
    if not message_lines:
        print("没有有效的单词数据")
        return False
        
    message = "\\n".join(message_lines)
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"https://ntfy.sh/{topic}",
                data=message,  # 不进行UTF-8编码
                headers={
                    "Title": f"GRE Words Review ({len(words_to_review)} words)",
                    "Priority": "high",
                    "Tags": "brain,study"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"成功发送 {len(words_to_review)} 个单词到 ntfy 主题: {topic}")
                return True
            else:
                print(f"ntfy 返回错误状态码: {response.status_code}")
                
        except Exception as e:
            print(f"推送失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    print(f"推送失败，已重试 {max_retries} 次")
    log_failed_notification(words_to_review)
    return False
'''
    
    return None

if __name__ == "__main__":
    # 读取配置
    try:
        with open('/root/gre_word_pusher/.env', 'r') as f:
            for line in f:
                if line.startswith('NTFY_TOPIC='):
                    topic = line.split('=', 1)[1].strip()
                    break
        else:
            topic = "gre-words-test"
    except:
        topic = "gre-words-test"
    
    print(f"🔧 使用主题: {topic}")
    
    # 测试不同方法
    successful_method = test_push_methods(topic, [])
    
    if successful_method:
        print(f"\n🎉 找到可用的推送方法: {successful_method}")
        fixed_function = create_fixed_push_function(successful_method)
        
        if fixed_function:
            print("\n📝 请将以下函数替换到 push_words.py 中:")
            print("="*60)
            print(fixed_function)
            print("="*60)
    else:
        print("\n❌ 无法找到可用的推送方法")
        print("建议检查网络连接和ntfy主题设置")
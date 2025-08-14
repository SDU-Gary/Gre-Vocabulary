#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送功能测试脚本
用于测试不同的推送方法和编码方案
"""

import requests
import json
import time
from datetime import datetime

def load_config():
    """加载配置"""
    config = {
        'ntfy_topic': 'gre-words-test',
        'csv_path': '/root/gre_word_pusher/words.csv'
    }
    
    try:
        with open('/root/gre_word_pusher/.env', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('NTFY_TOPIC='):
                    config['ntfy_topic'] = line.split('=', 1)[1].strip()
                elif line.startswith('GRE_CSV_PATH='):
                    config['csv_path'] = line.split('=', 1)[1].strip()
    except FileNotFoundError:
        print("⚠️ .env文件不存在，使用默认配置")
    except Exception as e:
        print(f"⚠️ 读取配置失败: {e}")
    
    return config

def test_basic_connectivity(topic):
    """测试基础连接性"""
    print("\n🔍 1. 测试基础连接性...")
    
    try:
        # 测试ntfy.sh主页
        response = requests.get("https://ntfy.sh", timeout=10)
        if response.status_code == 200:
            print("   ✅ ntfy.sh 服务可访问")
        else:
            print(f"   ❌ ntfy.sh 访问异常: {response.status_code}")
            return False
            
        # 测试主题端点
        response = requests.head(f"https://ntfy.sh/{topic}", timeout=10)
        if response.status_code in [200, 404]:  # 404也是正常的
            print(f"   ✅ 主题端点可访问: {topic}")
        else:
            print(f"   ❌ 主题端点异常: {response.status_code}")
            
        return True
        
    except Exception as e:
        print(f"   ❌ 连接测试失败: {e}")
        return False

def test_simple_english_push(topic):
    """测试简单英文推送"""
    print("\n🔍 2. 测试简单英文推送...")
    
    try:
        message = f"Test message at {datetime.now().strftime('%H:%M:%S')}"
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message,
            headers={
                "Title": "GRE Push Test",
                "Priority": "default",
                "Tags": "test"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ 英文推送成功")
            return True
        else:
            print(f"   ❌ 英文推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 英文推送异常: {e}")
        return False

def test_chinese_post_push(topic):
    """测试中文POST推送"""
    print("\n🔍 3. 测试中文POST推送...")
    
    try:
        message = f"测试中文消息 {datetime.now().strftime('%H:%M:%S')}\nubiquitous: 普遍存在的"
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode('utf-8'),
            headers={
                "Title": "GRE中文测试",
                "Priority": "default",
                "Tags": "test,chinese",
                "Content-Type": "text/plain; charset=utf-8"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ 中文POST推送成功")
            return True
        else:
            print(f"   ❌ 中文POST推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 中文POST推送异常: {e}")
        return False

def test_json_push(topic):
    """测试JSON格式推送"""
    print("\n🔍 4. 测试JSON格式推送...")
    
    try:
        payload = {
            "topic": topic,
            "message": f"JSON测试消息 {datetime.now().strftime('%H:%M:%S')}\n1. ubiquitous: 普遍存在的\n2. meticulous: 一丝不苟的",
            "title": "GRE JSON测试",
            "priority": "default",
            "tags": ["test", "json", "chinese"]
        }
        
        response = requests.post(
            "https://ntfy.sh/",
            json=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ JSON推送成功")
            return True
        else:
            print(f"   ❌ JSON推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ JSON推送异常: {e}")
        return False

def test_gre_words_format(topic):
    """测试GRE单词格式推送"""
    print("\n🔍 5. 测试GRE单词格式推送...")
    
    # 模拟真实的GRE单词数据
    words = [
        ["ubiquitous", "普遍存在的，无处不在的"],
        ["meticulous", "一丝不苟的，细致的"], 
        ["profound", "深刻的，深远的"],
        ["eloquent", "雄辩的，有说服力的"]
    ]
    
    try:
        # 构建消息
        message_lines = []
        for i, (word, definition) in enumerate(words, 1):
            message_lines.append(f"{i}. {word}: {definition}")
        
        message = "\n".join(message_lines)
        message += f"\n\n📚 共{len(words)}个单词\n💡 艾宾浩斯记忆曲线推送"
        
        # 使用JSON格式发送
        payload = {
            "topic": topic,
            "message": message,
            "title": f"🧠 GRE单词复习 ({len(words)}词)",
            "priority": "default",
            "tags": ["brain", "study", "gre"]
        }
        
        response = requests.post(
            "https://ntfy.sh/",
            json=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            print("   ✅ GRE单词格式推送成功")
            return True
        else:
            print(f"   ❌ GRE单词推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ GRE单词推送异常: {e}")
        return False

def main():
    """主测试流程"""
    print("🧪 GRE推送功能测试")
    print("="*50)
    
    # 加载配置
    config = load_config()
    topic = config['ntfy_topic']
    
    print(f"📋 配置信息:")
    print(f"   NTFY主题: {topic}")
    print(f"   CSV路径: {config['csv_path']}")
    
    # 运行测试
    tests = [
        ("基础连接", lambda: test_basic_connectivity(topic)),
        ("英文推送", lambda: test_simple_english_push(topic)),
        ("中文POST", lambda: test_chinese_post_push(topic)), 
        ("JSON推送", lambda: test_json_push(topic)),
        ("GRE格式", lambda: test_gre_words_format(topic))
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
            time.sleep(1)  # 避免请求过于频繁
        except Exception as e:
            print(f"   ❌ {test_name}测试出现异常: {e}")
            results[test_name] = False
    
    # 总结结果
    print("\n" + "="*50)
    print("📊 测试结果总结:")
    print("="*50)
    
    success_count = 0
    for test_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            success_count += 1
    
    print(f"\n📈 成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    # 给出建议
    print("\n💡 建议:")
    if results.get("JSON推送", False):
        print("   ✅ 推荐使用JSON格式推送（支持中文）")
        print("   📝 使用 push_words_fixed.py 替换原文件")
    elif results.get("中文POST", False):
        print("   ⚠️ 可以使用POST格式推送中文")
        print("   📝 需要在headers中指定UTF-8编码")
    elif results.get("英文推送", False):
        print("   ⚠️ 只能使用英文推送")
        print("   📝 建议暂时使用英文版本")
    else:
        print("   ❌ 所有推送方法都失败")
        print("   🔍 请检查网络连接和ntfy主题设置")
    
    print("\n🔧 如果测试成功，请在服务器上执行:")
    print("   cd /root/gre_word_pusher")
    print("   cp push_words.py push_words.py.backup")
    print("   cp push_words_fixed.py push_words.py")
    print("   python3 push_words.py")

if __name__ == "__main__":
    main()
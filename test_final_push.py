#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终推送方法测试脚本
基于测试结果调整推送策略
"""

import requests
import json
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

def test_simple_json_push(topic):
    """测试简化的JSON推送格式"""
    print("\n🔍 测试简化JSON推送格式...")
    
    try:
        # 构建测试消息
        message = f"测试简化JSON {datetime.now().strftime('%H:%M:%S')}\n1. ubiquitous: 普遍存在的\n2. meticulous: 一丝不苟的"
        
        payload = {
            "topic": topic,
            "message": message,
            "title": "🧠 GRE测试推送"
        }
        
        response = requests.post(
            "https://ntfy.sh/",
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ 简化JSON推送成功")
            return True
        else:
            print(f"   ❌ 简化JSON推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 简化JSON推送异常: {e}")
        return False

def test_encoded_post_push(topic):
    """测试编码后的POST推送"""
    print("\n🔍 测试编码POST推送...")
    
    try:
        message = f"测试编码POST {datetime.now().strftime('%H:%M:%S')}\n1. ubiquitous: 普遍存在的\n2. meticulous: 一丝不苟的"
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode('utf-8'),
            headers={
                "Title": "GRE编码测试".encode('utf-8').decode('latin-1'),
                "Priority": "default"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ 编码POST推送成功")
            return True
        else:
            print(f"   ❌ 编码POST推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 编码POST推送异常: {e}")
        return False

def test_english_fallback_push(topic):
    """测试英文降级推送"""
    print("\n🔍 测试英文降级推送...")
    
    try:
        message = f"English Fallback Test {datetime.now().strftime('%H:%M:%S')}\n1. ubiquitous\n2. meticulous\n\nCheck app for Chinese definitions."
        
        response = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message,
            headers={
                "Title": "GRE English Test",
                "Priority": "high",
                "Tags": "brain,study"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ 英文降级推送成功")
            return True
        else:
            print(f"   ❌ 英文降级推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 英文降级推送异常: {e}")
        return False

def main():
    """主测试流程"""
    print("🧪 最终推送方法测试")
    print("="*50)
    
    # 加载配置
    config = load_config()
    topic = config['ntfy_topic']
    
    print(f"📋 使用主题: {topic}")
    
    # 运行测试
    tests = [
        ("简化JSON", lambda: test_simple_json_push(topic)),
        ("编码POST", lambda: test_encoded_post_push(topic)),
        ("英文降级", lambda: test_english_fallback_push(topic))
    ]
    
    results = {}
    success_methods = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
            if result:
                success_methods.append(test_name)
            import time
            time.sleep(2)  # 避免请求过于频繁
        except Exception as e:
            print(f"   ❌ {test_name}测试出现异常: {e}")
            results[test_name] = False
    
    # 总结结果
    print("\n" + "="*50)
    print("📊 最终测试结果:")
    print("="*50)
    
    for test_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
    
    success_count = len(success_methods)
    print(f"\n📈 成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    # 推荐方案
    print("\n💡 推荐解决方案:")
    if "简化JSON" in success_methods:
        print("   🥇 使用简化JSON格式推送（最佳方案）")
        print("   📝 执行: cp push_words_final_fix.py push_words.py")
    elif "编码POST" in success_methods:
        print("   🥈 使用编码POST推送（备选方案）")
        print("   📝 需要调整头部编码处理")
    elif "英文降级" in success_methods:
        print("   🥉 使用英文降级推送（保底方案）")
        print("   📝 暂时只能推送英文单词")
    else:
        print("   ❌ 所有方法都失败，请检查网络和配置")
    
    print("\n🔧 下一步操作:")
    if success_methods:
        print("   1. cp push_words_final_fix.py push_words.py")
        print("   2. python3 push_words.py")
        print("   3. 检查手机是否收到推送")
    else:
        print("   1. 检查网络连接")
        print("   2. 验证ntfy主题设置")
        print("   3. 联系技术支持")

if __name__ == "__main__":
    main()
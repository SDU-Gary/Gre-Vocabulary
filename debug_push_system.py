#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送系统诊断脚本
全面检查定时推送系统的各个环节
"""

import os
import csv
import subprocess
import requests
from datetime import date, datetime, timedelta
import json

def check_environment():
    """检查系统环境"""
    print("🔍 系统环境检查")
    print("="*50)
    
    # 检查当前时间和时区
    print(f"当前系统时间: {datetime.now()}")
    
    try:
        result = subprocess.run(['timedatectl', 'status'], capture_output=True, text=True)
        print("时区设置:")
        print(result.stdout)
    except Exception as e:
        print(f"无法获取时区信息: {e}")
    
    # 检查Python环境
    print(f"Python版本: {subprocess.run(['python3', '--version'], capture_output=True, text=True).stdout.strip()}")
    
    # 检查必要的包
    packages = ['requests']
    for package in packages:
        try:
            __import__(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")

def check_crontab():
    """检查定时任务配置"""
    print("\n🕐 定时任务检查")
    print("="*50)
    
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            print("当前定时任务:")
            cron_lines = result.stdout.strip().split('\n')
            for line in cron_lines:
                if 'push_words' in line:
                    print(f"✅ 找到推送任务: {line}")
                else:
                    print(f"   {line}")
        else:
            print("❌ 没有找到定时任务")
            print("建议添加定时任务:")
            print("crontab -e")
            print("添加以下行:")
            print("0 8,12,18,21 * * 1-5 cd /root/gre_word_pusher && python3 push_words.py >> logs/cron.log 2>&1")
            print("0 9,14,20 * * 6,7 cd /root/gre_word_pusher && python3 push_words.py >> logs/cron.log 2>&1")
    except Exception as e:
        print(f"❌ 检查定时任务失败: {e}")

def check_files_and_permissions():
    """检查文件和权限"""
    print("\n📁 文件和权限检查")
    print("="*50)
    
    project_dir = "/root/gre_word_pusher"
    files_to_check = [
        "push_words.py",
        "safe_csv.py",
        "words.csv",
        ".env",
        "logs/cron.log"
    ]
    
    for file_path in files_to_check:
        full_path = os.path.join(project_dir, file_path)
        if os.path.exists(full_path):
            stat_info = os.stat(full_path)
            permissions = oct(stat_info.st_mode)[-3:]
            size = stat_info.st_size
            print(f"✅ {file_path} - 权限:{permissions}, 大小:{size}字节")
        else:
            print(f"❌ {file_path} - 文件不存在")
            
            # 特殊处理
            if file_path == "logs/cron.log":
                logs_dir = os.path.join(project_dir, "logs")
                if not os.path.exists(logs_dir):
                    print(f"   创建日志目录: {logs_dir}")
                    os.makedirs(logs_dir, exist_ok=True)

def check_configuration():
    """检查配置文件"""
    print("\n⚙️ 配置检查")
    print("="*50)
    
    config = {
        'ntfy_topic': None,
        'csv_path': '/root/gre_word_pusher/words.csv',
        'words_per_push': 15
    }
    
    # 从.env文件读取配置
    env_path = '/root/gre_word_pusher/.env'
    if os.path.exists(env_path):
        print(f"✅ 找到配置文件: {env_path}")
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NTFY_TOPIC='):
                        config['ntfy_topic'] = line.split('=', 1)[1].strip()
                        print(f"   NTFY主题: {config['ntfy_topic']}")
                    elif line.startswith('GRE_CSV_PATH='):
                        config['csv_path'] = line.split('=', 1)[1].strip()
                        print(f"   CSV路径: {config['csv_path']}")
                    elif line.startswith('WORDS_PER_PUSH='):
                        config['words_per_push'] = line.split('=', 1)[1].strip()
                        print(f"   推送单词数: {config['words_per_push']}")
        except Exception as e:
            print(f"❌ 读取配置文件失败: {e}")
    else:
        print(f"❌ 配置文件不存在: {env_path}")
    
    return config

def check_csv_data(csv_path):
    """检查CSV数据"""
    print("\n📊 单词数据检查")
    print("="*50)
    
    if not os.path.exists(csv_path):
        print(f"❌ CSV文件不存在: {csv_path}")
        return []
    
    try:
        words = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if len(row) >= 5:
                    words.append(row)
                else:
                    print(f"⚠️ 第{i+1}行数据格式不完整: {row}")
        
        print(f"✅ CSV文件包含 {len(words)} 个单词")
        
        # 分析需要复习的单词
        today = date.today()
        new_words = 0
        due_words = 0
        
        for word_data in words:
            try:
                word, definition, added_date, last_reviewed, review_count = word_data[:5]
                review_count = int(review_count)
                
                if review_count == 0:
                    new_words += 1
                else:
                    # 计算是否到期
                    if last_reviewed:
                        last_review_date = datetime.strptime(last_reviewed, '%Y-%m-%d').date()
                        # 简化的到期判断
                        intervals = [1, 2, 4, 7, 15, 30, 60]
                        interval = intervals[min(review_count, len(intervals) - 1)]
                        next_review = last_review_date + timedelta(days=interval)
                        
                        if today >= next_review:
                            due_words += 1
            except (ValueError, IndexError):
                continue
        
        print(f"   新单词: {new_words} 个")
        print(f"   到期复习: {due_words} 个")
        print(f"   总需复习: {new_words + due_words} 个")
        
        if new_words + due_words == 0:
            print("⚠️ 当前没有需要复习的单词！这可能是推送为空的原因。")
        
        return words[:5]  # 返回前5个单词作为样本
        
    except Exception as e:
        print(f"❌ 读取CSV文件失败: {e}")
        return []

def check_network_connectivity(ntfy_topic):
    """检查网络连接"""
    print("\n🌐 网络连接检查")
    print("="*50)
    
    if not ntfy_topic:
        print("❌ NTFY主题未设置，跳过网络测试")
        return False
    
    try:
        # 测试基本连接
        response = requests.get("https://ntfy.sh", timeout=10)
        if response.status_code == 200:
            print("✅ ntfy.sh 服务可访问")
        else:
            print(f"⚠️ ntfy.sh 返回状态码: {response.status_code}")
        
        # 测试推送
        test_message = f"推送系统测试 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        payload = {
            "topic": ntfy_topic,
            "message": test_message,
            "title": "🔧 系统测试"
        }
        
        response = requests.post(
            "https://ntfy.sh/",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if response.status_code == 200:
            print("✅ 测试推送发送成功")
            print("   请检查手机ntfy应用是否收到测试消息")
            return True
        else:
            print(f"❌ 测试推送失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")
        return False

def check_push_script():
    """检查推送脚本"""
    print("\n🐍 推送脚本检查")
    print("="*50)
    
    script_path = "/root/gre_word_pusher/push_words.py"
    
    if not os.path.exists(script_path):
        print(f"❌ 推送脚本不存在: {script_path}")
        return False
    
    try:
        # 尝试导入模块检查语法
        import sys
        sys.path.insert(0, "/root/gre_word_pusher")
        
        # 检查语法
        with open(script_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        compile(code, script_path, 'exec')
        print("✅ 推送脚本语法检查通过")
        
        # 尝试执行脚本（干运行）
        print("🔄 尝试执行推送脚本...")
        result = subprocess.run(
            ['python3', script_path], 
            cwd='/root/gre_word_pusher',
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ 推送脚本执行成功")
            print("执行输出:")
            print(result.stdout)
            if result.stderr:
                print("错误输出:")
                print(result.stderr)
        else:
            print(f"❌ 推送脚本执行失败 (返回码: {result.returncode})")
            print("错误输出:")
            print(result.stderr)
            if result.stdout:
                print("标准输出:")
                print(result.stdout)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ 脚本执行超时")
        return False
    except Exception as e:
        print(f"❌ 脚本检查失败: {e}")
        return False

def check_cron_logs():
    """检查cron日志"""
    print("\n📋 定时任务日志检查")
    print("="*50)
    
    log_paths = [
        "/root/gre_word_pusher/logs/cron.log",
        "/var/log/cron.log",
        "/var/log/syslog"
    ]
    
    for log_path in log_paths:
        if os.path.exists(log_path):
            print(f"✅ 找到日志文件: {log_path}")
            try:
                # 读取最后20行
                result = subprocess.run(
                    ['tail', '-20', log_path], 
                    capture_output=True, 
                    text=True
                )
                
                if result.stdout:
                    print(f"最近的日志内容:")
                    print(result.stdout)
                else:
                    print("日志文件为空")
                    
            except Exception as e:
                print(f"读取日志失败: {e}")
        else:
            print(f"❌ 日志文件不存在: {log_path}")

def provide_solutions():
    """提供解决方案"""
    print("\n💡 常见问题解决方案")
    print("="*50)
    
    solutions = [
        {
            "问题": "没有定时任务",
            "解决": "crontab -e\n添加: 0 8,12,18,21 * * * cd /root/gre_word_pusher && python3 push_words.py >> logs/cron.log 2>&1"
        },
        {
            "问题": "没有需要复习的单词",
            "解决": "添加新单词到CSV文件，或检查现有单词的复习日期"
        },
        {
            "问题": "网络推送失败",
            "解决": "检查NTFY_TOPIC设置，确认网络连接正常"
        },
        {
            "问题": "脚本执行失败",
            "解决": "检查Python依赖包，确认文件权限正确"
        },
        {
            "问题": "时区问题",
            "解决": "sudo timedatectl set-timezone Asia/Shanghai"
        }
    ]
    
    for solution in solutions:
        print(f"🔸 {solution['问题']}:")
        print(f"   {solution['解决']}")
        print()

def main():
    """主诊断流程"""
    print("🩺 GRE推送系统诊断工具")
    print("="*60)
    print(f"诊断时间: {datetime.now()}")
    print()
    
    # 执行所有检查
    check_environment()
    check_crontab()
    check_files_and_permissions()
    config = check_configuration()
    sample_words = check_csv_data(config['csv_path'])
    network_ok = check_network_connectivity(config['ntfy_topic'])
    script_ok = check_push_script()
    check_cron_logs()
    
    # 总结报告
    print("\n📋 诊断总结")
    print("="*50)
    
    issues = []
    
    if not config['ntfy_topic']:
        issues.append("❌ NTFY主题未配置")
    
    if not sample_words:
        issues.append("❌ 没有有效的单词数据")
    
    if not network_ok:
        issues.append("❌ 网络推送测试失败")
    
    if not script_ok:
        issues.append("❌ 推送脚本执行失败")
    
    if issues:
        print("发现的问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ 所有检查都通过了！")
        print("如果仍未收到推送，请:")
        print("1. 确认手机ntfy应用已订阅正确主题")
        print("2. 等待下一个定时推送时间")
        print("3. 手动执行: cd /root/gre_word_pusher && python3 push_words.py")
    
    provide_solutions()
    
    print("\n🔧 下一步操作建议:")
    print("1. 根据上述问题修复相关配置")
    print("2. 手动测试: python3 push_words.py")
    print("3. 重新运行诊断: python3 debug_push_system.py")

if __name__ == "__main__":
    main()
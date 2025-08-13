#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRE单词系统健康检查和监控工具
提供系统状态检查、数据完整性验证、配置检查等功能
"""

import os
import csv
import json
import time
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from safe_csv import get_csv_handler


class HealthChecker:
    """系统健康检查器"""
    
    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.csv_file_path = self.config.get('csv_file_path', '/home/your_user/gre_word_pusher/words.csv')
        self.ntfy_topic = self.config.get('ntfy_topic', 'gre-words-for-my-awesome-life-123xyz')
        self.results = []
    
    def _load_config(self, config_path):
        """加载配置文件"""
        default_config = {
            'csv_file_path': '/home/your_user/gre_word_pusher/words.csv',
            'ntfy_topic': 'gre-words-for-my-awesome-life-123xyz',
            'max_file_size_mb': 10,
            'min_free_space_mb': 100,
            'ntfy_timeout_seconds': 10
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"加载配置文件失败，使用默认配置: {e}")
        
        return default_config
    
    def check_file_system(self):
        """检查文件系统状态"""
        print("🔍 检查文件系统...")
        
        # 检查CSV文件
        try:
            csv_path = Path(self.csv_file_path)
            
            if not csv_path.exists():
                self.results.append(('ERROR', '数据文件不存在', f'CSV文件不存在: {csv_path}'))
                return False
            
            # 检查文件大小
            file_size_mb = csv_path.stat().st_size / 1024 / 1024
            max_size = self.config['max_file_size_mb']
            
            if file_size_mb > max_size:
                self.results.append(('WARNING', '文件过大', f'CSV文件大小: {file_size_mb:.2f}MB > {max_size}MB'))
            else:
                self.results.append(('OK', '文件大小正常', f'CSV文件大小: {file_size_mb:.2f}MB'))
            
            # 检查文件权限
            if not os.access(csv_path, os.R_OK | os.W_OK):
                self.results.append(('ERROR', '文件权限不足', '无法读写CSV文件'))
                return False
            else:
                self.results.append(('OK', '文件权限正常', '可读写CSV文件'))
            
            # 检查磁盘空间
            disk_usage = os.statvfs(csv_path.parent)
            free_space_mb = (disk_usage.f_bavail * disk_usage.f_frsize) / 1024 / 1024
            min_space = self.config['min_free_space_mb']
            
            if free_space_mb < min_space:
                self.results.append(('ERROR', '磁盘空间不足', f'剩余空间: {free_space_mb:.2f}MB < {min_space}MB'))
            else:
                self.results.append(('OK', '磁盘空间充足', f'剩余空间: {free_space_mb:.2f}MB'))
            
            return True
            
        except Exception as e:
            self.results.append(('ERROR', '文件系统检查失败', str(e)))
            return False
    
    def check_data_integrity(self):
        """检查数据完整性"""
        print("🔍 检查数据完整性...")
        
        try:
            csv_handler = get_csv_handler(self.csv_file_path)
            all_words = csv_handler.read_all_words()
            
            if not all_words:
                self.results.append(('WARNING', '数据为空', '没有找到单词数据'))
                return True
            
            total_words = len(all_words)
            valid_words = 0
            invalid_rows = []
            duplicate_words = set()
            word_set = set()
            
            for i, row in enumerate(all_words):
                # 检查行格式
                if len(row) < 5:
                    invalid_rows.append(f'行{i+1}: 列数不足({len(row)}<5)')
                    continue
                
                word, definition, added_date, last_reviewed_date, review_count = row
                
                # 检查必填字段
                if not word or not definition:
                    invalid_rows.append(f'行{i+1}: 单词或释义为空')
                    continue
                
                # 检查重复
                word_lower = word.lower()
                if word_lower in word_set:
                    duplicate_words.add(word)
                else:
                    word_set.add(word_lower)
                
                # 检查日期格式
                try:
                    datetime.strptime(added_date, '%Y-%m-%d')
                    datetime.strptime(last_reviewed_date, '%Y-%m-%d')
                except ValueError:
                    invalid_rows.append(f'行{i+1}: 日期格式错误')
                    continue
                
                # 检查复习次数
                try:
                    count = int(review_count)
                    if count < 0:
                        invalid_rows.append(f'行{i+1}: 复习次数为负数')
                        continue
                except ValueError:
                    invalid_rows.append(f'行{i+1}: 复习次数格式错误')
                    continue
                
                valid_words += 1
            
            # 报告结果
            if invalid_rows:
                error_msg = f'发现{len(invalid_rows)}个无效行: ' + '; '.join(invalid_rows[:5])
                if len(invalid_rows) > 5:
                    error_msg += f'... (还有{len(invalid_rows)-5}个)'
                self.results.append(('ERROR', '数据格式错误', error_msg))
            
            if duplicate_words:
                dup_msg = f'发现{len(duplicate_words)}个重复单词: ' + ', '.join(list(duplicate_words)[:5])
                if len(duplicate_words) > 5:
                    dup_msg += f'... (还有{len(duplicate_words)-5}个)'
                self.results.append(('WARNING', '重复数据', dup_msg))
            
            if valid_words > 0:
                self.results.append(('OK', '数据完整性检查', f'有效单词: {valid_words}/{total_words}'))
            
            return len(invalid_rows) == 0
            
        except Exception as e:
            self.results.append(('ERROR', '数据完整性检查失败', str(e)))
            return False
    
    def check_network_connectivity(self):
        """检查网络连接性"""
        print("🔍 检查网络连接...")
        
        try:
            timeout = self.config['ntfy_timeout_seconds']
            
            # 测试ntfy.sh连通性
            test_url = f"https://ntfy.sh/{self.ntfy_topic}"
            
            start_time = time.time()
            response = requests.head(test_url, timeout=timeout)
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                self.results.append(('OK', 'ntfy.sh连接正常', f'响应时间: {response_time}ms'))
                return True
            else:
                self.results.append(('WARNING', 'ntfy.sh响应异常', f'状态码: {response.status_code}'))
                return False
                
        except requests.exceptions.Timeout:
            self.results.append(('ERROR', '网络超时', f'ntfy.sh响应超时(>{timeout}s)'))
            return False
        except requests.exceptions.ConnectionError:
            self.results.append(('ERROR', '网络连接失败', '无法连接到ntfy.sh'))
            return False
        except Exception as e:
            self.results.append(('ERROR', '网络检查失败', str(e)))
            return False
    
    def check_system_resources(self):
        """检查系统资源"""
        print("🔍 检查系统资源...")
        
        try:
            import psutil
            
            # 检查内存使用
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self.results.append(('ERROR', '内存使用过高', f'内存使用率: {memory.percent:.1f}%'))
            elif memory.percent > 80:
                self.results.append(('WARNING', '内存使用较高', f'内存使用率: {memory.percent:.1f}%'))
            else:
                self.results.append(('OK', '内存使用正常', f'内存使用率: {memory.percent:.1f}%'))
            
            # 检查CPU使用（1秒采样）
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                self.results.append(('WARNING', 'CPU使用过高', f'CPU使用率: {cpu_percent:.1f}%'))
            else:
                self.results.append(('OK', 'CPU使用正常', f'CPU使用率: {cpu_percent:.1f}%'))
                
        except ImportError:
            self.results.append(('INFO', '系统资源监控', '需要安装psutil包以监控系统资源'))
        except Exception as e:
            self.results.append(('WARNING', '系统资源检查失败', str(e)))
    
    def check_service_status(self):
        """检查服务状态（如果在systemd环境下）"""
        print("🔍 检查服务状态...")
        
        try:
            # 检查systemd服务状态
            result = os.popen('systemctl is-active gre_app.service 2>/dev/null').read().strip()
            
            if result == 'active':
                self.results.append(('OK', 'Web服务状态', 'gre_app.service 运行正常'))
            elif result == 'inactive':
                self.results.append(('ERROR', 'Web服务停止', 'gre_app.service 未运行'))
            else:
                self.results.append(('WARNING', 'Web服务状态未知', f'gre_app.service 状态: {result}'))
                
        except Exception as e:
            self.results.append(('INFO', '服务状态检查', '无法检查systemd服务状态'))
    
    def run_full_check(self):
        """运行完整的健康检查"""
        print(f"🏥 开始系统健康检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        self.results = []
        
        # 执行各项检查
        checks = [
            self.check_file_system,
            self.check_data_integrity,
            self.check_network_connectivity,
            self.check_system_resources,
            self.check_service_status
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.results.append(('ERROR', f'{check.__name__}失败', str(e)))
        
        # 生成报告
        self.print_report()
        return self.get_overall_status()
    
    def print_report(self):
        """打印检查报告"""
        print("\n📋 健康检查报告")
        print("=" * 60)
        
        status_counts = {'OK': 0, 'WARNING': 0, 'ERROR': 0, 'INFO': 0}
        
        for status, title, message in self.results:
            status_counts[status] += 1
            
            icon = {
                'OK': '✅',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'INFO': 'ℹ️'
            }.get(status, '❓')
            
            print(f"{icon} [{status}] {title}: {message}")
        
        print("\n📊 检查总结")
        print(f"✅ 正常: {status_counts['OK']}")
        print(f"⚠️ 警告: {status_counts['WARNING']}")
        print(f"❌ 错误: {status_counts['ERROR']}")
        print(f"ℹ️ 信息: {status_counts['INFO']}")
        
        overall_status = self.get_overall_status()
        print(f"\n🎯 整体状态: {overall_status}")
    
    def get_overall_status(self):
        """获取整体健康状态"""
        error_count = sum(1 for status, _, _ in self.results if status == 'ERROR')
        warning_count = sum(1 for status, _, _ in self.results if status == 'WARNING')
        
        if error_count > 0:
            return f"❌ 异常 ({error_count}个错误)"
        elif warning_count > 0:
            return f"⚠️ 注意 ({warning_count}个警告)"
        else:
            return "✅ 健康"
    
    def save_report(self, output_file=None):
        """保存检查报告到文件"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"health_report_{timestamp}.json"
        
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': self.get_overall_status(),
            'results': [
                {'status': status, 'title': title, 'message': message}
                for status, title, message in self.results
            ]
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 报告已保存到: {output_file}")
        except Exception as e:
            print(f"\n❌ 保存报告失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GRE单词系统健康检查工具')
    parser.add_argument('--config', help='配置文件路径')
    parser.add_argument('--save', help='保存报告到文件')
    parser.add_argument('--quiet', action='store_true', help='静默模式，只显示结果')
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.config)
    
    if args.quiet:
        import sys
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        
        try:
            status = checker.run_full_check()
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout
        
        print(status)
    else:
        checker.run_full_check()
    
    if args.save:
        checker.save_report(args.save)


if __name__ == "__main__":
    main()
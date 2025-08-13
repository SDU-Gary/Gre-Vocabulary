#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全的CSV文件操作模块
解决并发读写竞态条件问题
"""

import csv
import fcntl
import os
import time
from contextlib import contextmanager
from typing import List, Optional, Tuple, Set


class SafeCSVHandler:
    """安全的CSV处理类，支持文件锁和错误恢复"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.backup_path = f"{file_path}.backup"
        
    def _ensure_file_exists(self):
        """确保CSV文件存在，不存在则创建"""
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # 写入CSV头部（可选）
                # writer.writerow(['word', 'definition', 'added_date', 'last_reviewed_date', 'review_count'])
    
    @contextmanager
    def _safe_file_lock(self, mode='r'):
        """安全的文件锁上下文管理器"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                f = open(self.file_path, mode, encoding='utf-8', newline='')
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield f
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()
                return
            except (IOError, OSError) as e:
                if f:
                    f.close()
                if attempt < max_retries - 1:
                    print(f"文件锁获取失败，重试 {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (2 ** attempt))  # 指数退避
                else:
                    raise Exception(f"无法获取文件锁，最大重试次数已达到: {e}")
    
    def read_all_words(self) -> List[List[str]]:
        """安全读取所有单词"""
        self._ensure_file_exists()
        
        try:
            with self._safe_file_lock('r') as f:
                return list(csv.reader(f))
        except Exception as e:
            print(f"读取CSV文件失败: {e}")
            return []
    
    def write_all_words(self, words_data: List[List[str]], create_backup: bool = True):
        """安全写入所有单词数据"""
        if create_backup and os.path.exists(self.file_path):
            self._create_backup()
        
        try:
            with self._safe_file_lock('w') as f:
                writer = csv.writer(f)
                writer.writerows(words_data)
        except Exception as e:
            print(f"写入CSV文件失败: {e}")
            if create_backup:
                self._restore_backup()
            raise
    
    def append_word(self, word_data: List[str]) -> bool:
        """安全追加单词"""
        try:
            with self._safe_file_lock('a') as f:
                writer = csv.writer(f)
                writer.writerow(word_data)
            return True
        except Exception as e:
            print(f"追加单词失败: {e}")
            return False
    
    def word_exists(self, word: str) -> bool:
        """检查单词是否存在（优化版本，避免全文件读取）"""
        word_lower = word.lower()
        try:
            with self._safe_file_lock('r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and row[0].lower() == word_lower:
                        return True
            return False
        except Exception as e:
            print(f"检查单词存在性失败: {e}")
            return False
    
    def _create_backup(self):
        """创建备份文件"""
        try:
            if os.path.exists(self.file_path):
                import shutil
                shutil.copy2(self.file_path, self.backup_path)
        except Exception as e:
            print(f"创建备份失败: {e}")
    
    def _restore_backup(self):
        """从备份恢复文件"""
        try:
            if os.path.exists(self.backup_path):
                import shutil
                shutil.copy2(self.backup_path, self.file_path)
                print("已从备份恢复CSV文件")
        except Exception as e:
            print(f"从备份恢复失败: {e}")


# 全局CSV处理器实例（单例模式）
_csv_handler = None

def get_csv_handler(file_path: str) -> SafeCSVHandler:
    """获取CSV处理器实例（单例）"""
    global _csv_handler
    if _csv_handler is None or _csv_handler.file_path != file_path:
        _csv_handler = SafeCSVHandler(file_path)
    return _csv_handler
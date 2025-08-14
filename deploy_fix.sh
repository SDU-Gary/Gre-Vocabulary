#!/bin/bash
# GRE推送功能修复部署脚本
# 用于修复中文编码问题和时区问题

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 配置变量
PROJECT_DIR="/root/gre_word_pusher"

echo "🔧 GRE推送功能修复脚本"
echo "================================"

# 检查项目目录
if [[ ! -d "$PROJECT_DIR" ]]; then
    error "项目目录不存在: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"
info "当前目录: $(pwd)"

# 1. 修复时区设置
info "修复时区设置..."
if timedatectl list-timezones | grep -q "Asia/Shanghai"; then
    sudo timedatectl set-timezone Asia/Shanghai
    success "时区已设置为中国标准时间"
else
    warning "无法设置时区，请手动执行: sudo timedatectl set-timezone Asia/Shanghai"
fi

echo "当前时间: $(date)"

# 2. 备份原文件
info "备份原始文件..."
if [[ -f "push_words.py" ]]; then
    cp push_words.py "push_words.py.backup.$(date +%Y%m%d_%H%M%S)"
    success "已备份原始推送脚本"
fi

if [[ -f "app.py" ]]; then
    cp app.py "app.py.backup.$(date +%Y%m%d_%H%M%S)"
    success "已备份原始Web应用"
fi

# 3. 检查是否有新文件需要部署
info "检查修复文件..."
files_to_deploy=(
    "push_words_fixed.py"
    "test_push.py"
    "app.py"
    "templates/index.html"
)

missing_files=()
for file in "${files_to_deploy[@]}"; do
    if [[ ! -f "$file" ]]; then
        missing_files+=("$file")
    fi
done

if [[ ${#missing_files[@]} -gt 0 ]]; then
    warning "以下文件缺失，需要从git同步:"
    for file in "${missing_files[@]}"; do
        echo "  - $file"
    done
    echo
    info "请先执行 git pull 获取最新文件，然后重新运行此脚本"
    exit 1
fi

# 4. 部署修复文件
info "部署修复后的文件..."

if [[ -f "push_words_fixed.py" ]]; then
    cp push_words_fixed.py push_words.py
    success "已更新推送脚本"
fi

# 5. 测试推送功能
info "测试推送功能..."
if python3 test_push.py > test_results.log 2>&1; then
    success "推送测试完成，查看结果: cat test_results.log"
else
    warning "推送测试可能有问题，查看详情: cat test_results.log"
fi

# 6. 手动测试实际推送
info "执行实际推送测试..."
if python3 push_words.py > manual_test.log 2>&1; then
    success "手动推送测试完成"
    if grep -q "成功发送" manual_test.log; then
        success "✅ 推送功能正常工作"
    else
        warning "推送可能有问题，查看日志: cat manual_test.log"
    fi
else
    error "手动推送测试失败，查看日志: cat manual_test.log"
fi

# 7. 更新定时任务（如果需要）
info "检查定时任务..."
if crontab -l 2>/dev/null | grep -q "push_words.py"; then
    success "定时任务已存在"
    
    # 显示当前定时任务
    echo "当前定时任务:"
    crontab -l | grep push_words.py || true
    
    # 询问是否需要调整时间
    echo
    warning "建议的推送时间（中国时间）:"
    echo "  工作日: 8:00, 12:00, 18:00, 21:00"
    echo "  周末: 9:00, 14:00, 20:00"
    echo
    echo "如需修改推送时间，请手动执行: crontab -e"
else
    warning "未发现定时任务，建议添加:"
    echo "  crontab -e"
    echo "  添加以下行:"
    echo "  0 8,12,18,21 * * 1-5 cd $PROJECT_DIR && python3 push_words.py >> logs/cron.log 2>&1"
    echo "  0 9,14,20 * * 6,7 cd $PROJECT_DIR && python3 push_words.py >> logs/cron.log 2>&1"
fi

# 8. 检查Web服务状态
info "检查Web服务状态..."
if systemctl is-active gre_app.service >/dev/null 2>&1; then
    success "Web服务正在运行"
    
    # 重启服务以应用任何更改
    info "重启Web服务以应用更改..."
    sudo systemctl restart gre_app.service
    
    if systemctl is-active gre_app.service >/dev/null 2>&1; then
        success "Web服务重启成功"
    else
        error "Web服务重启失败"
        sudo systemctl status gre_app.service || true
    fi
else
    warning "Web服务未运行"
    info "尝试启动Web服务..."
    sudo systemctl start gre_app.service
fi

# 9. 运行健康检查
info "运行系统健康检查..."
if python3 health_check.py > health_report.log 2>&1; then
    success "健康检查完成"
    
    # 显示关键信息
    if grep -q "整体状态" health_report.log; then
        echo "健康状态: $(grep "整体状态" health_report.log | tail -1)"
    fi
else
    warning "健康检查异常，查看详情: cat health_report.log"
fi

# 10. 显示总结
echo
echo "🎉 修复部署完成！"
echo "=================="

echo
echo "📱 下一步操作:"
echo "1. 在手机ntfy应用中确认已订阅正确的主题"
echo "2. 测试是否能收到推送消息"
echo "3. 如果推送正常，系统将按中国时间自动推送"

echo
echo "🔧 有用的命令:"
echo "- 手动测试推送: cd $PROJECT_DIR && python3 push_words.py"
echo "- 查看推送日志: tail -f $PROJECT_DIR/logs/cron.log"
echo "- 查看Web服务状态: sudo systemctl status gre_app.service"
echo "- 运行健康检查: cd $PROJECT_DIR && python3 health_check.py"

echo
echo "📊 推送时间安排 (中国时间):"
echo "- 工作日: 8:00, 12:00, 18:00, 21:00"
echo "- 周末: 9:00, 14:00, 20:00"

echo
if [[ -f "test_results.log" ]]; then
    echo "📋 推送测试结果概要:"
    if grep -q "成功率" test_results.log; then
        grep "成功率" test_results.log | tail -1
    fi
    
    if grep -q "建议" test_results.log; then
        echo
        echo "💡 测试建议:"
        grep -A 5 "建议:" test_results.log | tail -5
    fi
fi

success "修复部署脚本执行完成！"
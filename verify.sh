#!/bin/bash
# GRE单词管理系统部署验证脚本
# 用于验证部署是否成功

set -euo pipefail

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# 配置
PROJECT_DIR="$HOME/gre_word_pusher"
REQUIRED_FILES=(
    "safe_csv.py"
    "app.py" 
    "push_words.py"
    "health_check.py"
    "templates/login.html"
    "templates/index.html"
    "templates/stats.html"
    "templates/error.html"
    "words.csv"
    ".env"
)

OPTIONAL_FILES=(
    "gre_app.service"
    "logs/"
    "backups/"
    ".env.example"
    "DEPLOY.md"
)

# 检查计数器
checks_passed=0
checks_total=0

check() {
    local description="$1"
    local command="$2"
    
    ((checks_total++))
    info "检查: $description"
    
    if eval "$command" &>/dev/null; then
        success "$description"
        ((checks_passed++))
        return 0
    else
        error "$description"
        return 1
    fi
}

# 验证项目目录
verify_project_structure() {
    info "验证项目结构..."
    
    if [[ ! -d "$PROJECT_DIR" ]]; then
        error "项目目录不存在: $PROJECT_DIR"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    success "项目目录存在: $PROJECT_DIR"
    
    # 检查必需文件
    info "检查必需文件..."
    for file in "${REQUIRED_FILES[@]}"; do
        if [[ -e "$file" ]]; then
            success "文件存在: $file"
            ((checks_passed++))
        else
            error "文件缺失: $file"
        fi
        ((checks_total++))
    done
    
    # 检查可选文件
    info "检查可选文件..."
    for file in "${OPTIONAL_FILES[@]}"; do
        if [[ -e "$file" ]]; then
            success "可选文件存在: $file"
        else
            warning "可选文件缺失: $file"
        fi
    done
}

# 验证Python环境
verify_python_environment() {
    info "验证Python环境..."
    
    check "Python3 可用" "command -v python3"
    check "pip3 可用" "command -v pip3"
    
    # 检查Python包
    local packages=("flask" "gunicorn" "requests")
    for package in "${packages[@]}"; do
        check "$package 已安装" "python3 -c 'import $package'"
    done
    
    # 检查Python语法
    local python_files=("safe_csv.py" "app.py" "push_words.py" "health_check.py")
    for file in "${python_files[@]}"; do
        if [[ -f "$file" ]]; then
            check "$file 语法检查" "python3 -m py_compile $file"
        fi
    done
}

# 验证配置文件
verify_configuration() {
    info "验证配置文件..."
    
    if [[ -f ".env" ]]; then
        success ".env 配置文件存在"
        
        # 检查关键配置项
        local required_vars=("GRE_SECRET_KEY" "GRE_PASSWORD" "GRE_CSV_PATH" "NTFY_TOPIC")
        for var in "${required_vars[@]}"; do
            if grep -q "^$var=" .env && ! grep -q "^$var=$\|^$var=change-me\|^$var=your-" .env; then
                success "配置项已设置: $var"
                ((checks_passed++))
            else
                warning "配置项需要修改: $var"
            fi
            ((checks_total++))
        done
    else
        error "配置文件不存在: .env"
        ((checks_total++))
    fi
}

# 验证数据文件
verify_data_file() {
    info "验证数据文件..."
    
    if [[ -f "words.csv" ]]; then
        check "数据文件存在" "test -f words.csv"
        check "数据文件可读" "test -r words.csv"
        check "数据文件可写" "test -w words.csv"
        
        # 检查CSV格式
        if python3 -c "
import csv
try:
    with open('words.csv', 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)
        print(f'CSV格式正确，包含 {len(rows)} 行数据')
except Exception as e:
    print(f'CSV格式错误: {e}')
    exit(1)
" 2>/dev/null; then
            success "CSV文件格式正确"
            ((checks_passed++))
        else
            error "CSV文件格式错误"
        fi
        ((checks_total++))
    else
        error "数据文件不存在: words.csv"
        ((checks_total++))
    fi
}

# 验证网络连接
verify_network() {
    info "验证网络连接..."
    
    check "互联网连接" "curl -Is https://ntfy.sh --connect-timeout 5"
    
    # 测试ntfy主题（如果配置了）
    if [[ -f ".env" ]] && grep -q "NTFY_TOPIC=" .env; then
        local topic=$(grep "NTFY_TOPIC=" .env | cut -d'=' -f2)
        if [[ -n "$topic" && "$topic" != "your-topic-name" ]]; then
            check "ntfy主题可访问" "curl -Is https://ntfy.sh/$topic --connect-timeout 5"
        fi
    fi
}

# 验证systemd服务
verify_service() {
    info "验证systemd服务..."
    
    if command -v systemctl &>/dev/null; then
        if systemctl list-unit-files | grep -q gre_app.service; then
            success "systemd服务已安装"
            
            if systemctl is-enabled gre_app.service &>/dev/null; then
                success "服务已设置开机自启"
                ((checks_passed++))
            else
                warning "服务未设置开机自启"
            fi
            ((checks_total++))
            
            if systemctl is-active gre_app.service &>/dev/null; then
                success "服务正在运行"
                ((checks_passed++))
            else
                warning "服务未运行"
            fi
            ((checks_total++))
            
        else
            warning "systemd服务未安装"
            ((checks_total++))
        fi
    else
        info "systemd不可用，跳过服务检查"
    fi
}

# 验证Web应用
verify_web_app() {
    info "验证Web应用..."
    
    # 检查端口8000
    if netstat -tln 2>/dev/null | grep -q ":8000 "; then
        success "端口8000正在监听"
        
        # 测试HTTP响应
        if curl -Is http://localhost:8000 --connect-timeout 5 --max-time 10 2>/dev/null | head -1 | grep -q "200\|302"; then
            success "Web应用响应正常"
            ((checks_passed++))
        else
            warning "Web应用响应异常"
        fi
        ((checks_total++))
        
        ((checks_passed++))
    else
        warning "端口8000未监听，Web应用可能未启动"
        ((checks_total++))
    fi
}

# 验证定时任务
verify_cron() {
    info "验证定时任务..."
    
    if crontab -l 2>/dev/null | grep -q "push_words.py"; then
        success "推送定时任务已设置"
        ((checks_passed++))
    else
        warning "推送定时任务未设置"
    fi
    ((checks_total++))
}

# 运行健康检查
run_health_check() {
    info "运行系统健康检查..."
    
    if [[ -f "health_check.py" ]]; then
        if python3 health_check.py --quiet 2>/dev/null; then
            success "健康检查通过"
            ((checks_passed++))
        else
            warning "健康检查发现问题"
        fi
        ((checks_total++))
    else
        warning "健康检查脚本不存在"
        ((checks_total++))
    fi
}

# 显示结果摘要
show_summary() {
    echo
    echo "🏁 验证完成！"
    echo "======================="
    
    local success_rate=$(( checks_passed * 100 / checks_total ))
    
    echo "✅ 通过: $checks_passed/$checks_total ($success_rate%)"
    
    if [[ $success_rate -ge 90 ]]; then
        success "🎉 部署验证成功！系统运行良好"
    elif [[ $success_rate -ge 70 ]]; then
        warning "⚠️ 部署基本成功，但有一些警告需要注意"
    else
        error "❌ 部署存在问题，请检查上述错误信息"
        exit 1
    fi
    
    echo
    echo "📝 下一步建议："
    echo "1. 在手机上测试推送通知"
    echo "2. 通过Web界面添加测试单词"
    echo "3. 检查定时推送是否正常工作"
    echo "4. 配置防火墙和SSL证书（可选）"
    
    echo
    echo "🔧 有用的命令："
    echo "- Web界面: http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'your-server-ip'):8000"
    echo "- 健康检查: cd $PROJECT_DIR && python3 health_check.py"
    echo "- 手动推送: cd $PROJECT_DIR && python3 push_words.py"
    echo "- 查看日志: sudo journalctl -u gre_app.service -f"
}

# 主函数
main() {
    echo "🔍 GRE单词管理系统部署验证"
    echo "=============================="
    echo
    
    verify_project_structure
    verify_python_environment  
    verify_configuration
    verify_data_file
    verify_network
    verify_service
    verify_web_app
    verify_cron
    run_health_check
    
    show_summary
}

# 执行验证
main "$@"
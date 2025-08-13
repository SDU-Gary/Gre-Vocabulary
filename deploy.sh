#!/bin/bash
# GRE单词管理系统一键部署脚本
# 作者: Claude Code
# 版本: v2.0 安全增强版

set -euo pipefail  # 严格错误处理

# 颜色输出函数
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 配置变量
PROJECT_DIR="$HOME/gre_word_pusher"
SERVICE_NAME="gre_app.service"
PYTHON_BIN="python3"
PIP_BIN="pip3"

# 检查函数
check_python() {
    if ! command -v $PYTHON_BIN &> /dev/null; then
        error "Python3 未安装，请先安装 Python 3.7+"
        exit 1
    fi
    
    local python_version=$($PYTHON_BIN --version 2>&1 | cut -d' ' -f2)
    info "Python 版本: $python_version"
}

check_pip() {
    if ! command -v $PIP_BIN &> /dev/null; then
        error "pip3 未安装，正在尝试安装..."
        sudo apt-get update && sudo apt-get install -y python3-pip
    fi
}

check_systemd() {
    if ! command -v systemctl &> /dev/null; then
        warning "systemd 不可用，将跳过服务安装"
        return 1
    fi
    return 0
}

# 创建项目目录
setup_directories() {
    info "创建项目目录..."
    
    mkdir -p "$PROJECT_DIR"/{templates,logs,backups}
    cd "$PROJECT_DIR"
    
    success "项目目录创建完成: $PROJECT_DIR"
}

# 安装依赖
install_dependencies() {
    info "安装Python依赖包..."
    
    # 创建requirements.txt
    cat > requirements.txt << EOF
Flask>=2.0.1
gunicorn>=20.1.0
requests>=2.25.1
psutil>=5.8.0
EOF
    
    $PIP_BIN install -r requirements.txt --user
    
    success "Python依赖安装完成"
}

# 复制文件
copy_files() {
    info "复制项目文件..."
    
    # 检查当前目录是否有项目文件
    local current_dir=$(pwd)
    local files_to_copy=(
        "safe_csv.py"
        "push_words.py" 
        "app.py"
        "health_check.py"
        "templates/login.html"
        "templates/index.html"
        "templates/stats.html"
        "templates/error.html"
        "gre_app.service"
        ".env.example"
    )
    
    for file in "${files_to_copy[@]}"; do
        if [[ -f "$current_dir/$file" ]]; then
            cp "$current_dir/$file" "$PROJECT_DIR/$file" 2>/dev/null || true
        else
            warning "文件不存在，跳过: $file"
        fi
    done
    
    success "项目文件复制完成"
}

# 配置环境变量
setup_environment() {
    info "配置环境变量..."
    
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env" 2>/dev/null || {
            warning "环境配置模板不存在，创建基本配置..."
            
            # 生成随机密钥
            local secret_key=$(openssl rand -hex 32 2>/dev/null || echo "change-me-$(date +%s)")
            local random_password="gre$(date +%s | tail -c 6)"
            
            cat > "$PROJECT_DIR/.env" << EOF
GRE_SECRET_KEY=$secret_key
GRE_PASSWORD=$random_password
GRE_CSV_PATH=$PROJECT_DIR/words.csv
NTFY_TOPIC=gre-words-$(whoami)-$(date +%s)
PYTHONPATH=$PROJECT_DIR
EOF
            
            warning "请编辑 $PROJECT_DIR/.env 修改配置"
            warning "默认密码: $random_password"
        }
    fi
    
    success "环境配置完成"
}

# 创建初始CSV文件
setup_csv() {
    info "初始化数据文件..."
    
    local csv_file="$PROJECT_DIR/words.csv"
    if [[ ! -f "$csv_file" ]]; then
        # 创建示例数据
        cat > "$csv_file" << EOF
ubiquitous,普遍存在的,2024-01-01,2024-01-01,0
meticulous,一丝不苟的,2024-01-01,2024-01-01,0
profound,深刻的,2024-01-01,2024-01-01,0
EOF
        success "数据文件初始化完成，包含3个示例单词"
    else
        info "数据文件已存在，跳过初始化"
    fi
}

# 设置文件权限
setup_permissions() {
    info "设置文件权限..."
    
    # 设置目录权限
    chmod 755 "$PROJECT_DIR"
    chmod 755 "$PROJECT_DIR/templates"
    
    # 设置Python文件权限
    find "$PROJECT_DIR" -name "*.py" -exec chmod 644 {} \;
    chmod +x "$PROJECT_DIR/health_check.py"
    
    # 设置数据文件权限
    chmod 666 "$PROJECT_DIR/words.csv" 2>/dev/null || true
    
    success "文件权限设置完成"
}

# 安装systemd服务
install_service() {
    if ! check_systemd; then
        return
    fi
    
    info "安装systemd服务..."
    
    # 替换服务文件中的用户名和路径
    local service_file="$PROJECT_DIR/gre_app.service"
    if [[ -f "$service_file" ]]; then
        sed -i "s|your_user|$(whoami)|g" "$service_file"
        sed -i "s|/home/your_user/gre_word_pusher|$PROJECT_DIR|g" "$service_file"
        
        sudo cp "$service_file" "/etc/systemd/system/$SERVICE_NAME"
        sudo systemctl daemon-reload
        
        success "systemd服务安装完成"
    else
        warning "服务配置文件不存在，跳过systemd安装"
    fi
}

# 设置定时任务
setup_cron() {
    info "设置定时推送任务..."
    
    # 检查是否已有相关的cron任务
    if crontab -l 2>/dev/null | grep -q "push_words.py"; then
        warning "检测到已有的定时任务，跳过设置"
        return
    fi
    
    # 创建新的cron任务
    local cron_job="0 8,10,12,14,16,18,20,22 * * * cd $PROJECT_DIR && $PYTHON_BIN push_words.py >> logs/cron.log 2>&1"
    
    (crontab -l 2>/dev/null; echo "$cron_job") | crontab -
    
    success "定时推送任务设置完成（每2小时推送一次，8:00-22:00）"
}

# 运行健康检查
run_health_check() {
    info "运行系统健康检查..."
    
    cd "$PROJECT_DIR"
    if $PYTHON_BIN health_check.py --quiet; then
        success "健康检查通过"
    else
        warning "健康检查发现问题，请查看详细信息："
        $PYTHON_BIN health_check.py || true
    fi
}

# 启动服务
start_services() {
    if ! check_systemd; then
        info "手动启动Web应用..."
        info "运行命令: cd $PROJECT_DIR && gunicorn --workers 1 --bind 0.0.0.0:8000 app:app"
        return
    fi
    
    info "启动Web服务..."
    
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl start $SERVICE_NAME
    
    # 检查服务状态
    if sudo systemctl is-active $SERVICE_NAME &>/dev/null; then
        success "Web服务启动成功"
        info "访问地址: http://$(hostname -I | awk '{print $1}'):8000"
    else
        error "Web服务启动失败，检查日志："
        sudo systemctl status $SERVICE_NAME || true
    fi
}

# 显示后续步骤
show_next_steps() {
    echo
    echo "🎉 部署完成！"
    echo "=================="
    
    echo
    echo "📱 下一步操作："
    echo "1. 在手机上安装ntfy应用"
    echo "2. 订阅你的主题（查看 $PROJECT_DIR/.env 中的 NTFY_TOPIC）"
    echo "3. 访问Web界面添加单词: http://$(hostname -I | awk '{print $1}'):8000"
    echo "4. 登录密码在 $PROJECT_DIR/.env 文件中"
    
    echo
    echo "🔧 管理命令："
    echo "- 查看服务状态: sudo systemctl status $SERVICE_NAME"
    echo "- 重启服务: sudo systemctl restart $SERVICE_NAME"
    echo "- 查看日志: sudo journalctl -u $SERVICE_NAME -f"
    echo "- 健康检查: cd $PROJECT_DIR && python3 health_check.py"
    echo "- 手动推送: cd $PROJECT_DIR && python3 push_words.py"
    
    echo
    echo "📁 重要文件："
    echo "- 配置文件: $PROJECT_DIR/.env"
    echo "- 数据文件: $PROJECT_DIR/words.csv"
    echo "- 日志目录: $PROJECT_DIR/logs/"
    
    echo
    echo "⚠️  安全提醒："
    echo "- 请修改 $PROJECT_DIR/.env 中的密码和密钥"
    echo "- 建议配置防火墙只允许必要的端口"
    echo "- 定期备份 words.csv 文件"
}

# 主函数
main() {
    echo "🚀 GRE单词管理系统部署脚本 v2.0"
    echo "=================================="
    
    # 检查运行环境
    check_python
    check_pip
    
    # 执行部署步骤
    setup_directories
    install_dependencies
    copy_files
    setup_environment
    setup_csv
    setup_permissions
    install_service
    setup_cron
    run_health_check
    start_services
    
    # 显示后续步骤
    show_next_steps
}

# 错误处理
trap 'error "部署过程中发生错误，请检查输出信息"' ERR

# 执行主函数
main "$@"
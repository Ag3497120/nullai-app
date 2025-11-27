#!/bin/bash
#
# NullAI 起動スクリプト
#
# 使用方法:
#   ./start_null_ai.sh          # 全サービス起動
#   ./start_null_ai.sh backend  # バックエンドのみ
#   ./start_null_ai.sh frontend # フロントエンドのみ
#   ./start_null_ai.sh ollama   # Ollamaのみ
#   ./start_null_ai.sh stop     # 全サービス停止

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# バナー表示
show_banner() {
    echo ""
    echo -e "${BLUE}"
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║                                                           ║"
    echo "  ║    ███╗   ██╗██╗   ██╗██╗     ██╗          █████╗ ██╗    ║"
    echo "  ║    ████╗  ██║██║   ██║██║     ██║         ██╔══██╗██║    ║"
    echo "  ║    ██╔██╗ ██║██║   ██║██║     ██║         ███████║██║    ║"
    echo "  ║    ██║╚██╗██║██║   ██║██║     ██║         ██╔══██║██║    ║"
    echo "  ║    ██║ ╚████║╚██████╔╝███████╗███████╗    ██║  ██║██║    ║"
    echo "  ║    ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚══════╝    ╚═╝  ╚═╝╚═╝    ║"
    echo "  ║                                                           ║"
    echo "  ║                                                           ║"
    echo "  ║         Multi-Domain Knowledge Reasoning System           ║"
    echo "  ║                     Version 1.0.0                         ║"
    echo "  ║                                                           ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

# 依存関係チェック
check_dependencies() {
    log_info "Checking dependencies..."

    # Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_success "Python 3: $(python3 --version)"

    # Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed"
        exit 1
    fi
    log_success "Node.js: $(node --version)"

    # Ollama (オプション)
    if command -v ollama &> /dev/null; then
        log_success "Ollama: installed"
    else
        log_warn "Ollama is not installed (required for local LLM)"
    fi

    echo ""
}

# 仮想環境のアクティベート
activate_venv() {
    if [ -d "venv" ]; then
        source venv/bin/activate
        log_success "Virtual environment activated"
    else
        log_warn "Virtual environment not found. Creating..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt 2>/dev/null || log_warn "requirements.txt not found"
    fi
}

# Ollamaの起動
start_ollama() {
    log_info "Starting Ollama..."

    if ! command -v ollama &> /dev/null; then
        log_error "Ollama is not installed"
        return 1
    fi

    # 既に起動しているか確認
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        log_success "Ollama is already running"
        return 0
    fi

    # バックグラウンドで起動
    ollama serve &> /tmp/ollama.log &
    OLLAMA_PID=$!
    echo $OLLAMA_PID > /tmp/ollama.pid

    # 起動待ち
    sleep 2
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        log_success "Ollama started (PID: $OLLAMA_PID)"
    else
        log_error "Failed to start Ollama"
        return 1
    fi
}

# バックエンドの起動
start_backend() {
    log_info "Starting Backend API..."

    activate_venv

    # データベース初期化（必要な場合）
    if [ ! -f "sql_app.db" ]; then
        log_info "Initializing database..."
        "$SCRIPT_DIR/venv/bin/python" backend/create_db.py 2>/dev/null || true
    fi

    # uvicornで起動（仮想環境のPythonを明示的に使用）
    cd "$SCRIPT_DIR"
    "$SCRIPT_DIR/venv/bin/python" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &> /tmp/backend.log &
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/backend.pid

    sleep 2
    if curl -s http://localhost:8000/health &> /dev/null; then
        log_success "Backend started (PID: $BACKEND_PID)"
        log_info "API Docs: http://localhost:8000/docs"
    else
        log_warn "Backend may still be starting..."
    fi
}

# フロントエンドの起動
start_frontend() {
    log_info "Starting Frontend..."

    cd "$SCRIPT_DIR/frontend"

    # 依存関係インストール
    if [ ! -d "node_modules" ]; then
        log_info "Installing frontend dependencies..."
        npm install
    fi

    # Vite開発サーバー起動
    npm run dev &> /tmp/frontend.log &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /tmp/frontend.pid

    cd "$SCRIPT_DIR"

    sleep 3
    log_success "Frontend started (PID: $FRONTEND_PID)"
    log_info "Frontend: http://localhost:5173"
}

# 全サービス停止
stop_all() {
    log_info "Stopping all services..."

    # Backend
    if [ -f /tmp/backend.pid ]; then
        kill $(cat /tmp/backend.pid) 2>/dev/null || true
        rm /tmp/backend.pid
        log_success "Backend stopped"
    fi

    # Frontend
    if [ -f /tmp/frontend.pid ]; then
        kill $(cat /tmp/frontend.pid) 2>/dev/null || true
        rm /tmp/frontend.pid
        log_success "Frontend stopped"
    fi

    # Ollama
    if [ -f /tmp/ollama.pid ]; then
        kill $(cat /tmp/ollama.pid) 2>/dev/null || true
        rm /tmp/ollama.pid
        log_success "Ollama stopped"
    fi

    log_success "All services stopped"
}

# ステータス表示
show_status() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                    NullAI Status                        ║"
    echo "╠═══════════════════════════════════════════════════════════╣"

    # Ollama
    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo -e "║  Ollama:    ${GREEN}Running${NC}  http://localhost:11434            ║"
    else
        echo -e "║  Ollama:    ${RED}Stopped${NC}                                      ║"
    fi

    # Backend
    if curl -s http://localhost:8000/health &> /dev/null; then
        echo -e "║  Backend:   ${GREEN}Running${NC}  http://localhost:8000             ║"
    else
        echo -e "║  Backend:   ${RED}Stopped${NC}                                      ║"
    fi

    # Frontend
    if curl -s http://localhost:5173 &> /dev/null; then
        echo -e "║  Frontend:  ${GREEN}Running${NC}  http://localhost:5173             ║"
    else
        echo -e "║  Frontend:  ${RED}Stopped${NC}                                      ║"
    fi

    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
}

# メイン処理
main() {
    show_banner

    case "${1:-all}" in
        all)
            check_dependencies
            start_ollama
            start_backend
            start_frontend
            show_status
            log_success "NullAI is ready!"
            echo ""
            echo "Press Ctrl+C to stop watching logs, or run './start_null_ai.sh stop' to stop all services"
            echo ""
            # ログを表示
            tail -f /tmp/backend.log /tmp/frontend.log 2>/dev/null
            ;;
        backend)
            check_dependencies
            start_backend
            show_status
            tail -f /tmp/backend.log 2>/dev/null
            ;;
        frontend)
            start_frontend
            show_status
            tail -f /tmp/frontend.log 2>/dev/null
            ;;
        ollama)
            start_ollama
            ;;
        stop)
            stop_all
            ;;
        status)
            show_status
            ;;
        *)
            echo "Usage: $0 {all|backend|frontend|ollama|stop|status}"
            exit 1
            ;;
    esac
}

main "$@"

#!/bin/bash
# 抖音直播录音系统 - systemd 服务管理脚本

SERVICE_NAME="dy-live-recorder"
SERVICE_FILE="/workspace/dy-live-recorder/dy-live-recorder.service"

install_service() {
    echo "安装 systemd 服务..."
    
    if [ ! -f "$SERVICE_FILE" ]; then
        echo "错误: 服务文件不存在: $SERVICE_FILE"
        exit 1
    fi
    
    cp "$SERVICE_FILE" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    
    echo "服务安装完成！"
}

uninstall_service() {
    echo "卸载 systemd 服务..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null
    systemctl disable "$SERVICE_NAME" 2>/dev/null
    rm /etc/systemd/system/"$SERVICE_NAME".service
    systemctl daemon-reload
    echo "服务已卸载"
}

case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        systemctl start "$SERVICE_NAME"
        ;;
    stop)
        systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        systemctl restart "$SERVICE_NAME"
        ;;
    status)
        systemctl status "$SERVICE_NAME"
        ;;
    logs)
        journalctl -u "$SERVICE_NAME" -f --no-pager
        ;;
    *)
        echo "用法: $0 {install|uninstall|start|stop|restart|status|logs}"
        echo ""
        echo "命令说明:"
        echo "  install   - 安装服务（需要root权限）"
        echo "  uninstall - 卸载服务（需要root权限）"
        echo "  start     - 启动服务"
        echo "  stop      - 停止服务"
        echo "  restart   - 重启服务"
        echo "  status    - 查看服务状态"
        echo "  logs      - 查看实时日志"
        exit 1
        ;;
esac

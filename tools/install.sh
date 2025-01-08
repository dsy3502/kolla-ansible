#!/bin/bash

# 检查参数
if [ $# -ne 2 ]; then
    echo "用法: $0 <username> <password>"
    exit 1
fi

# 检查sshpass
if ! command -v sshpass &> /dev/null; then
    echo "错误: 请安装 sshpass"
    echo "Windows WSL/Ubuntu: sudo apt install sshpass"
    exit 1
fi

USERNAME=$1
PASSWORD=$2
INVENTORY_FILE="./inventory/multinode"

# 检查inventory文件
if [ ! -f "$INVENTORY_FILE" ]; then
    echo "错误: 未找到inventory文件!"
    exit 1
fi

# 提取并处理[all]段中的主机
sed -n '/^\[all\]/,/^\[/p' "$INVENTORY_FILE" | 
    grep "ansible_host" | 
    grep -v "^#" | 
    while IFS=' =' read -r hostname _ ip _; do
        echo "处理主机: $hostname ($ip)"
        
        # 修改主机名
        if ! sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$USERNAME@$ip" \
            "sudo hostnamectl set-hostname $hostname"; then
            echo "主机名修改失败: $hostname"
            continue
        fi
        
        # 生成SSH密钥
        [ ! -f ~/.ssh/id_rsa ] && ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
        
        # 配置SSH互信
        if ! sshpass -p "$PASSWORD" ssh-copy-id -o StrictHostKeyChecking=no "$USERNAME@$ip"; then
            echo "SSH互信配置失败: $hostname"
            continue
        fi
        
        echo "完成配置: $hostname"
    done

echo "全部配置完成！"

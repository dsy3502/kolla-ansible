#!/bin/bash

# 检查参数
if [ $# -ne 2 ]; then
    echo "用法: $0 <username> <password>"
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

# 提取主机名和IP的映射关系
declare -A HOST_IP_MAP
while read -r line; do
    if [[ $line =~ ^[^#;].*ansible_host= ]]; then
        hostname=$(echo "$line" | awk '{print $1}')
        ip=$(echo "$line" | awk -F'=' '{print $2}')
        HOST_IP_MAP[$hostname]=$ip
    fi
done < "$INVENTORY_FILE"

# 读取control和compute节点
get_nodes() {
    local section=$1
    awk "/\[$section\]/{flag=1;next}/\[.*\]/{flag=0}flag" "$INVENTORY_FILE" | 
    grep -v '^#' | grep -v '^$' | grep -v 'ansible_'
}

# 合并control和compute节点
NODES=$(get_nodes "control")
NODES+=$'\n'$(get_nodes "compute")

# 去重
UNIQUE_NODES=$(echo "$NODES" | sort -u)

# 处理每个节点
echo "$UNIQUE_NODES" | while read -r hostname; do
    if [ -z "$hostname" ]; then continue; fi
    
    IP="${HOST_IP_MAP[$hostname]}"
    if [ -z "$IP" ]; then
        echo "警告: 找不到 $hostname 的IP地址"
        continue
    fi
    
    echo "正在配置节点: $hostname ($IP)"
    
    # 修改主机名
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$USERNAME@$IP" \
        "sudo hostnamectl set-hostname $hostname" || {
        echo "修改主机名失败: $hostname"
        continue
    }
    
    # 确保本地SSH密钥存在
    if [ ! -f ~/.ssh/id_rsa ]; then
        ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
    fi
    
    # 配置SSH互信
    sshpass -p "$PASSWORD" ssh-copy-id -o StrictHostKeyChecking=no "$USERNAME@$IP" || {
        echo "SSH互信配置失败: $hostname"
        continue
    }
    
    echo "节点 $hostname ($IP) 配置完成"
done

echo "所有节点配置完成！"
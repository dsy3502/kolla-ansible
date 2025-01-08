#!/usr/bin/env python3

import configparser
import os
import subprocess
import sys
from typing import Dict, Tuple

def parse_inventory(inventory_path: str) -> Dict[str, str]:
    """解析inventory文件中[all]段的主机信息"""
    hosts = {}
    
    with open(inventory_path, 'r') as f:
        lines = f.readlines()
    
    in_all_section = False
    for line in lines:
        line = line.strip()
        
        # 判断是否在[all]段
        if line == '[all]':
            in_all_section = True
            continue
        elif line.startswith('[') and in_all_section:
            break
            
        # 解析主机信息
        if in_all_section and line and not line.startswith('#'):
            if 'ansible_host=' in line:
                parts = line.split()
                hostname = parts[0]
                ip = parts[1].split('=')[1]
                hosts[hostname] = ip
    
    return hosts

def configure_host(hostname: str, ip: str, username: str, password: str) -> bool:
    """配置主机名和SSH互信"""
    try:
        # 修改主机名
        cmd = f'sshpass -p {password} ssh -o StrictHostKeyChecking=no {username}@{ip} "sudo hostnamectl set-hostname {hostname}"'
        subprocess.run(cmd, shell=True, check=True)
        
        # 配置SSH互信
        if not os.path.exists(os.path.expanduser('~/.ssh/id_rsa')):
            subprocess.run('ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa', shell=True, check=True)
        
        cmd = f'sshpass -p {password} ssh-copy-id -o StrictHostKeyChecking=no {username}@{ip}'
        subprocess.run(cmd, shell=True, check=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"配置失败 {hostname}: {str(e)}")
        return False

def main():
    if len(sys.argv) != 3:
        print("用法: python install.py <username> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    inventory_path = './inventory/multinode'
    
    if not os.path.exists(inventory_path):
        print(f"错误: 未找到inventory文件: {inventory_path}")
        sys.exit(1)
    
    hosts = parse_inventory(inventory_path)
    for hostname, ip in hosts.items():
        print(f"配置主机: {hostname} ({ip})")
        if configure_host(hostname, ip, username, password):
            print(f"完成配置: {hostname}")
        else:
            print(f"配置失败: {hostname}")

if __name__ == '__main__':
    main()


import nmap
import paramiko
import argparse
import ipaddress
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
import os

def scan_ip_range(ip_range: str) -> list:
    """扫描指定IP范围内的存活主机"""
    nm = nmap.PortScanner()
    nm.scan(hosts=ip_range, arguments='-sn')
    return sorted([host for host in nm.all_hosts()])

def get_interface_name(ip: str, username: str, password: str, ip_range: str) -> str:
    """获取主机的默认网卡名称"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=username, password=password, timeout=5)
         # 获取所有网卡信息
        cmd = "ip -o addr show | grep 'inet ' | awk '{print $2,$4}'"
        stdin, stdout, stderr = client.exec_command(cmd)
        interfaces = stdout.read().decode().strip().split('\n')
        
        # 解析网卡信息
        for interface in interfaces:
            if not interface:
                continue
            iface_name, iface_ip = interface.split()
            iface_ip = iface_ip.split('/')[0]  # 移除CIDR前缀
            if is_ip_in_range(iface_ip, ip_range):
                client.close()
                return iface_name
        
        # 如果没有匹配的网卡，返回默认路由的网卡
        cmd = "ip route | grep default | awk '{print $5}'"
        stdin, stdout, stderr = client.exec_command(cmd)
        default_interface = stdout.read().decode().strip()
        
        client.close()
        return default_interface or "eth0" 
    except Exception as e:
        print(f"获取网卡名称失败 for {ip}: {str(e)}")
        return "eth0"
def get_neutron_interface_name(ip: str, username: str, password: str, ip_range: str) -> str:
    """获取主机上没有配置IP的网卡名称"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, username=username, password=password, timeout=5)

        # 获取所有网卡名称
        cmd = "ip link show | grep -v 'link' | awk '{print $2}' | sed 's/://' | grep -v lo"
        stdin, stdout, stderr = client.exec_command(cmd)
        all_interfaces = stdout.read().decode().strip().split('\n')

        # 获取已配置IP的网卡
        cmd = "ip -o addr show | grep 'inet ' | awk '{print $2}'"
        stdin, stdout, stderr = client.exec_command(cmd)
        used_interfaces = stdout.read().decode().strip().split('\n')

        # 找出未配置IP的网卡
        unused_interfaces = [iface for iface in all_interfaces if iface not in used_interfaces]
        
        client.close()
        # 返回第一个未使用的网卡，如果没有则返回eth1
        return unused_interfaces[0] if unused_interfaces else "eth1"
        
    except Exception as e:
        print(f"获取网卡名称失败 for {ip}: {str(e)}")
        return "eth1"
    
def is_ip_in_range(ip: str, ip_range: str) -> bool:
    """判断IP是否在给定范围内"""
    try:
        if '-' in ip_range:
            # 处理范围格式 (如: 192.168.1.1-10)
            base_ip = ip_range.split('-')[0].rsplit('.', 1)[0]
            start = ip_range.split('-')[0].split('.')[-1]
            end = ip_range.split('-')[1]
            start_ip = f"{base_ip}.{start}"
            end_ip = f"{base_ip}.{end}"
            return ipaddress.ip_address(ip) >= ipaddress.ip_address(start_ip) and \
                   ipaddress.ip_address(ip) <= ipaddress.ip_address(end_ip)
        elif '/' in ip_range:
            # 处理CIDR格式
            return ipaddress.ip_address(ip) in ipaddress.ip_network(ip_range)
        return ip == ip_range
    except ValueError as e:
        print(f"IP范围检查失败: {str(e)}")
        return False

def write_inventory(hosts: list, username: str, password: str, ip_range: str, output_file: str = "inventory", control_count: int = 3, shared: bool = False) -> None:
    
        try:
                    # Create data loader
                    loader = DataLoader()
                    
                    # Create inventory manager
                    if os.path.exists(output_file):
                        inventory = InventoryManager(loader=loader, sources=output_file)
                    else:
                        inventory = InventoryManager(loader=loader)
                        
                    # Create required groups
                    inventory.add_group('control')
                    inventory.add_group('compute')
                        
                    # Add or update hosts
                    for index, ip in enumerate(hosts, start=1):
                        hostname = f"openstack{index}"
                        interface = get_interface_name(ip, username, password, ip_range)
                        
                        # Add host to all group with variables
                        inventory.add_host(hostname, group='all')
                        host = inventory.get_host(hostname)
                        host.set_variable('ansible_host', ip)
                        host.set_variable('ansible_user', username)
                        host.set_variable('ansible_password', password)
                        host.set_variable('network_interface', interface)
                        
                        # Add host to control/compute groups based on parameters
                        if index <= control_count:
                            inventory.add_host(hostname, group='control')
                        if shared or index > control_count:
                            inventory.add_host(hostname, group='compute')
                    neutron_interface = get_neutron_interface_name(ip, username, password, ip_range)
                    # Save inventory
                    with open(output_file, 'w') as f:
                        f.write("[all]\n")
                        for host in inventory.get_hosts(pattern='all'):
                            vars_str = ' '.join([f'{k}={v}' for k, v in host.get_vars().items() if k.startswith('ansible_') or k == 'network_interface'])
                            f.write(f"{host.name} {vars_str}\n")

                        f.write("\n[control]\n")
                        for host in inventory.get_hosts(pattern='control'):
                            #vars_str = ' '.join([f'{k}={v}' for k, v in host.get_vars().items() if k.startswith('ansible_') or k == 'network_interface'])
                            f.write(f"{host.name}\n")
                            
                        f.write("\n[compute]\n")
                        for host in inventory.get_hosts(pattern='compute'):
                            #vars_str = ' '.join([f'{k}={v}' for k, v in host.get_vars().items() if k.startswith('ansible_') or k == 'network_interface'])
                            f.write(f"{host.name} neutron_external_interface={neutron_interface}\n")
                    
                    print(f"Successfully updated inventory file: {output_file}")
                    print(f"Added {len(hosts)} hosts")
                    
        except Exception as e:
                    print(f"Failed to update inventory file: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description='扫描IP范围内的存活主机')
    parser.add_argument('ip_range', help='IP范围 (例如: 10.220.57.20-30 或 10.220.57.0/24)')
    parser.add_argument('username', help='SSH用户名')
    parser.add_argument('password', help='SSH密码')
    parser.add_argument('--output', '-o', default='inventory', help='输出文件路径')
    parser.add_argument('--control-count', '-c', type=int, default=3, help='控制节点数量')
    parser.add_argument('--shared', '-s', action='store_true', help='控制节点是否同时作为计算节点')
    args = parser.parse_args()

    hosts = scan_ip_range(args.ip_range)
    write_inventory(hosts, args.username, args.password, args.ip_range, args.output, 3, True)

if __name__ == '__main__':
    main()


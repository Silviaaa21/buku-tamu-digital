import os
import json
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA_DIR = os.environ.get("DATA_DIR", "/data")
DATA_FILE = os.path.join(DATA_DIR, "guestbook.json")

def init_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        atomic_write([])

def atomic_write(data):
    """Menulis data secara atomik: tulis ke file temp lalu rename"""
    temp_file = f"{DATA_FILE}.{uuid.uuid4().hex}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, DATA_FILE)

def read_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

class GuestbookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Mematikan log default BaseHTTPRequestHandler agar konsisten memakai JSON
        pass

    def emit_json_log(self, status_code, start_time):
        latency_ms = round((time.time() - start_time) * 1000, 2)
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": self.command,
            "path": self.path,
            "status": status_code,
            "latency_ms": latency_ms,
            "client_ip": self.headers.get("X-Real-IP", self.client_address[0])
        }
        print(json.dumps(log_entry), flush=True)

    def send_json_response(self, status_code, data, start_time):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.emit_json_log(status_code, start_time)

    def do_GET(self):
        start_time = time.time()
        
        # 1. Health check endpoint
        if self.path == "/health":
            self.send_json_response(200, {"status": "healthy"}, start_time)
            return

        # 2. Get messages endpoint
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ["/api/messages", "/messages"]:
            messages = read_data()
            self.send_json_response(200, messages, start_time)
            return

        self.send_json_response(404, {"error": "Not Found"}, start_time)

    def do_POST(self):
        start_time = time.time()
        clean_path = self.path.split("?")[0].rstrip("/")
        
        if clean_path in ["/api/messages", "/messages"]:
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_length)
                payload = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self.send_json_response(400, {"error": "Format JSON tidak valid"}, start_time)
                return

            entry_id = str(payload.get("id") or uuid.uuid4().hex[:8])
            created_at = payload.get("at") or datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
            nama_tamu = payload.get("nama", "").strip()

            if not nama_tamu:
                self.send_json_response(400, {"error": "Nama wajib diisi"}, start_time)
                return

            new_entry = {
                "id": entry_id,
                "nama": nama_tamu,
                "instansi": payload.get("instansi") or payload.get("fak", "").strip(),
                "pesan": payload.get("pesan") or payload.get("review", "").strip(),
                "at": created_at,
                "role": payload.get("role", "mhs"),
                "nim": payload.get("nim", ""),
                "prodi": payload.get("prodi", ""),
                "mhs": payload.get("mhs", ""),
                "rating": payload.get("rating", 5),
                "photos": payload.get("photos", [])
            }

            current_data = read_data()
            current_data.insert(0, new_entry)
            atomic_write(current_data)

            # Response JSON dilengkapi 'message' untuk pop-up/toast frontend
            response_payload = {
                "success": True,
                "message": f"Data kunjungan atas nama '{nama_tamu}' berhasil ditambahkan!",
                "data": new_entry
            }
            self.send_json_response(201, response_payload, start_time)
            return

        self.send_json_response(404, {"error": "Not Found"}, start_time)

    def do_DELETE(self):
        start_time = time.time()
        clean_path = self.path.split("?")[0].rstrip("/")
        parts = clean_path.split("/")

        if len(parts) >= 3 and parts[-2] == "messages":
            target_id = parts[-1]
            current_data = read_data()
            
            # Cari data sebelum dihapus untuk mengambil nama tamu
            target_entry = next((item for item in current_data if str(item.get("id")) == str(target_id)), None)

            if not target_entry:
                self.send_json_response(404, {"error": "Data tamu tidak ditemukan"}, start_time)
                return

            new_data = [item for item in current_data if str(item.get("id")) != str(target_id)]
            atomic_write(new_data)

            # Response JSON dilengkapi 'message' untuk pop-up/toast frontend
            response_payload = {
                "success": True,
                "message": f"Data kunjungan '{target_entry.get('nama')}' berhasil dihapus permanen.",
                "deleted_id": target_id
            }
            self.send_json_response(200, response_payload, start_time)
            return

        self.send_json_response(404, {"error": "Not Found"}, start_time)

def run(server_class=HTTPServer, handler_class=GuestbookHandler, port=5000):
    init_storage()
    server_address = ("0.0.0.0", port)
    httpd = server_class(server_address, handler_class)
    print(f"Backend berjalan di port {port}...", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    run()
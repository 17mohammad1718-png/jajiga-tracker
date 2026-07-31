"""
Server for Jajiga Tracker Dashboard
Usage: python server.py
Then open: http://localhost:8080
"""

import http.server, json, os, sys

PORT = 8080
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)
    
    def end_headers(self):
        # CORS for local dev
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == '__main__':
    print(f"\n  🏡 Jajiga Tracker Dashboard")
    print(f"  ─────────────────────────")
    print(f"  📂 Serving: {DIR}")
    print(f"  🌐 Open:    http://localhost:{PORT}/dashboard.html")
    print(f"  📄 Data:    http://localhost:{PORT}/data/all-cabins.json")
    print(f"  ⏹  Ctrl+C to stop\n")
    
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Server stopped.")
        server.server_close()

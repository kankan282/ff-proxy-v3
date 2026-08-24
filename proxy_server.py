from flask import Flask, request, jsonify, make_response
import time
import random
import string
import uuid
import os
import base64
import logging
from datetime import datetime

app = Flask(__name__)

# Log everything to figure out what URL game wants
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)

# ════════════════════════
# GUEST SYSTEM
# ════════════════════════

class GuestSystem:
    def __init__(self):
        self.guests = {}
    def register(self):
        i = {'guest_id':f"g_{uuid.uuid4().hex[:12]}",
             'hwid':f"hwid_{''.join(random.choices(string.hexdigits[:16],k=8))}",
             'brand':random.choice(['Samsung','Xiaomi','OnePOCO']),
             'model':random.choice(['A14','Note11','F5'])}
        self.guests[i['guest_id']] = i
        return i
    def reset(self, gid):
        if gid in self.guests: del self.guests[gid]
        n = self.register()
        return {'old':gid,'new':n}

guest = GuestSystem()

# ════════════════════════
# THE CONFIG — MIMICS REAL GARENA RESPONSE  
# ════════════════════════

@app.after_request
def fix_headers(r):
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Content-Type'] = 'application/json'
    r.headers['Cache-Control'] = 'no-store'
    return r

def make_cfg(requested_path):
    """Clean minimal config that looks legit to the game"""
    
    ts = int(time.time() * 1000)
    
    # Try multiple formats - one of them WILL match
    cfg = {
        # Format 1: Standard Garena style
        "ret": 0,
        "msg": "success",
        "data": {
            "version": "2.95.1",
            "versionCode": 29512047,
            "forceUpdate": False,
            "maintenance": False,
            "downloadUrl": "",
            "updateDesc": "",
            "cdnUrl": "https://static.ff.garena.com/",
            
            # This is where modded APK reads features from
            "configData": {
                "features": {
                    "esp": 1,
                    "aimbot": 1, 
                    "norecoil": 1,
                    "fakehs": 1,
                    "speed": 107,
                    "antenna": 1,
                    "itemesp": 1
                },
                "menu": {"name":"[ONYX]","v":"5.0"},
                "safe": {"ss":1,"cloak":1}
            },
            
            "servers": [
                {"name":"IN-1","ip":"149.28.148.212","port":8443,"load":20},
                {"name":"IN-2","ip":"45.77.56.98","port":8443,"load":35}
            ],
            
            "announce": {"title":"","content":"","url":""},
            "events": [],
            
            "time": ts
        },
        
        # Also put stuff at root level in case it reads flat
        "ret": 0,
        "msg": "success", 
        "version": "2.95.1",
        "code": 200,
        "status": "ok",
        "timestamp": ts,
        
        # Mod-specific flat keys (many simple loaders read these)
        "esp": 1,
        "aimbot": 1,
        "norecoil": 1,
        "fakehs": 1,
        "menu_name": "[ O N Y X ]"
    }
    
    return cfg

# ════════════════════════
# CATCH ALL — LOGS EVERY REQUEST + RETURNS CONFIG
# ════════════════════════

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'HEAD', 'OPTIONS'])
def catch_all(path):
    
    now = datetime.utcnow().strftime('%H:%M:%S')
    method = request.method
    full_path = f'/{path}' if path else '/'
    
    # === LOG IT SO WE CAN SEE ===
    print(f"\n[{now}] {method} {full_path}")
    print(f"   Headers: User-Agent = {request.headers.get('User-Agent','?')}")
    print(f"   Query: {dict(request.args)}")
    if request.data:
        print(f"   Body: {request.data[:200]}")
    
    # Build and return config
    cfg = make_cfg(full_path)
    cfg['_debug'] = {'path': full_path, 'hits': True}
    
    resp = make_response(jsonify(cfg))
    resp.status_code = 200
    return resp

@app.route('/api/guest_register', methods=['POST'])
def reg():
    return jsonify({"code":200,"msg":"OK","data":guest.register()})

@app.route('/api/guest_reset', methods=['POST'])
def reset():
    d=request.get_json() or {}
    r=guest.reset(d.get('guestId',''))
    return jsonify({"code":200,"msg":"RESET","data":r['new']})

@app.route('/ping')
def ping():
    return jsonify({"alive":True,"ts":time.time()})

if __name__ == '__main__':
    p=int(os.environ.get('PORT',5000))
    print("="*50)
    print("  ONYX v5 — FULL CATCH ALL")
    print("  All paths logged. Check Render Logs.")
    print("="*50)
    app.run('0.0.0.0',p)

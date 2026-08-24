from flask import Flask, request, jsonify, make_response
import time
import random
import string
import uuid
import os
import base64
from datetime import datetime

app = Flask(__name__)

# ════════════════════════
# REAL GARENA CONFIG FORMAT
# ════════════════════════

class GuestSystem:
    def __init__(self):
        self.guests = {}
        self.resets_today = 0

    def generate_identity(self):
        prefixes = ['hwid_samsung_','hwid_xiaomi_','hwid_realme_',
                     'hwid_oneplus_','hwid_poco_','hwid_vivo_']
        return {
            'guest_id': f"guest_{uuid.uuid4().hex[:16]}",
            'hwid': f"{random.choice(prefixes)}{''.join(random.choices(string.hexdigits[:16],k=8))}",
            'android_id': base64.b64encode(os.urandom(8)).decode().replace('=','').replace('/','0'),
            'device_brand': random.choice(['Samsung','Xiaomi','realme','OnePlus','POCO']),
            'device_model': random.choice(['SM-A145F','M2010J19SG','RMX3085']),
            'android_ver': random.choice(['11','12','13']),
        }

    def register(self):
        ident = self.generate_identity()
        self.guests[ident['guest_id']] = ident
        return ident

    def reset(self, old_gid):
        if old_gid in self.guests:
            del self.guests[old_gid]
        new = self.register()
        self.resets_today += 1
        return {'old': old_gid, 'new': new}

guest_sys = GuestSystem()

# ════════════════════════
# THE ACTUAL CONFIG FF EXPECTS
# ════════════════════════

def build_real_config():
    """
    Real Free Fire config JSON format.
    This mimics official Garena config server response.
    """
    return {
        "version": "2.95.1",
        "code": 200,
        "status": "ok",
        
        # Game reads these directly
        "gameConfig": {
            "region": "IN",
            "maintenance": False,
            "forceUpdate": False,
            "latestVersion": "2.95.1",
            "downloadUrl": "",
            
            # Feature flags (what mod loaders hook into)
            "featureFlags": {
                "esp_enabled": True,
                "aimbot_enabled": True,
                "norecoil_enabled": True,
                "fake_hs_enabled": True,
                "speedhack_enabled": True,
                "antiban_enabled": True,
                "menu_version": "4.3",
                "menu_name": "[ O N Y X ]"
            },
            
            # Mod payload (this gets loaded by modded APK)
            "modPayload": {
                "combat": {
                    "aimbot": {"active": 1, "fov": 90, "smooth": 3, "silent": 1},
                    "fakeHS": {"active": 1, "visualOnly": 1, "rate": 65},
                    "noRecoil": 1,
                    "noSpread": 1
                },
                "visual": {
                    "esp": {"active": 1, "box": 1, "hp": 1, "name": 1, "dist": 1, "line": 1},
                    "antenna": 1,
                    "itemEsp": 1
                },
                "player": {"speed": 107, "noFallDmg": 1},
                "safe": {"ssClean": 1, "cloakStats": 1, "shadowAuto": 1}
            }
        },
        
        # Standard Garena fields (required for game to proceed)
        "cdnUrls": {
            "resourceBase": "https://static.ff.garena.com/",
            "configBase": "https://static.ff.garena.com/config/"
        },
        "servers": [
            {"region": "IN", "ip": "game.ff.garena.com", "port": 8443, "load": 30}
        ],
        "announce": "",
        "announceUrl": "",
        "eventList": [],
        
        # Timestamp for freshness check
        "timestamp": int(time.time() * 1000)
    }


@app.after_request
def add_headers(response):
    """Fix CORS and content-type for game compatibility"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, HEAD'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


# ════════════════════════
# CATCH ALL + SPECIFIC ROUTES  
# ════════════════════════

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'HEAD', 'OPTIONS'])
def catch_all(path):
    """Every single URL returns valid config"""
    
    print(f"[{datetime.utcnow().isoformat()}] {request.method} /{path} | {request.remote_addr}")
    
    cfg = build_real_config()
    cfg['_requested_path'] = '/' + path if path else '/'
    
    resp = make_response(jsonify(cfg))
    resp.status_code = 200
    return resp


@app.route('/api/guest_register', methods=['POST'])
def guest_register():
    ident = guest_sys.register()
    return jsonify({"code": 200, "msg": "OK", "data": ident})

@app.route('/api/guest_reset', methods=['POST'])
def guest_reset():
    data = request.get_json() or {}
    old_gid = data.get('guestId') or data.get('guest_id') or ''
    result = guest_sys.reset(old_gid)
    ni = result['new']
    return jsonify({
        "code": 200, "msg": "RESET_OK",
        "data": ni,
        "_note": "Update HWID in localconfig.json then restart"
    })

@app.route('/ping')
def ping():
    return jsonify({"alive": True, "ts": time.time(), "svc": "onyx_v5"})

@app.route('/health')
def health():
    return jsonify({"ok": True, "g": len(guest_sys.guests), "ts": time.time()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

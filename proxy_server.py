from flask import Flask, request, jsonify
import json
import time
import random
import string
import uuid
import os
import base64
from datetime import datetime

app = Flask(__name__)

# ════════════════════════════════════
# GUEST SYSTEM
# ════════════════════════════════════

class GuestSystem:
    def __init__(self):
        self.guests = {}
        self.resets_today = 0
        
    def generate_identity(self):
        prefixes = ['hwid_samsung_', 'hwid_xiaomi_', 'hwid_realme_',
                     'hwid_oneplus_', 'hwid_poco_', 'hwid_vivo_']
        return {
            'guest_id': f"guest_{uuid.uuid4().hex[:16]}",
            'hwid': f"{random.choice(prefixes)}{''.join(random.choices(string.hexdigits[:16], k=8))}",
            'android_id': base64.b64encode(os.urandom(8)).decode().replace('=','').replace('/','0'),
            'advertising_id': str(uuid.uuid4()),
            'gaid': f"{uuid.uuid4()}",
            'mac_address': f"{random.choice(['A4:83:E7','34:DF:3A','CC:B2:55','E0:D7:82'])}:{':'.join(f'{random.randint(0,255):02X}' for _ in range(3))}",
            'imei': f"35{random.randint(10000000,99999999)}{random.randint(1000000,9999999)}",
            'serial': ''.join(random.choices(string.ascii_uppercase + string.digits, k=12)),
            'device_brand': random.choice(['Samsung','Xiaomi','realme','OnePlus','POCO','vivo','OPPO']),
            'device_model': random.choice(['SM-A145F','M2010J19SG','RMX3085','AC2001']),
            'android_ver': random.choice(['11','12','13']),
            'created': time.time()
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
        return {'old_abandoned': old_gid, 'new_identity': new}

guest_sys = GuestSystem()

# ════════════════════════════════════
# ROUTES
# ════════════════════════════════════

@app.route('/')
def root():
    return jsonify({
        "status": "online",
        "service": "ONYX_FF_v4",
        "time": datetime.utcnow().isoformat(),
        "active_guests": len(guest_sys.guests),
        "endpoints": {
            "payload": "/api/payload or /ff/payload",
            "register": "/api/guest_register (POST)",
            "reset": "/api/guest_reset (POST)"
        }
    })

@app.route('/api/payload')
@app.route('/ff/payload')
@app.route('/v1/config')
@app.route('/config')
def payload():
    hwid = request.args.get('hwid', 'unknown')
    region = request.args.get('region', 'IN')
    sid = request.args.get('sid', '')
    gid = request.args.get('gid', '')
    
    resp = {
        "_meta": {
            "server": "ONYX v4",
            "timestamp": int(time.time()),
            "region": region,
            "session": sid
        },
        "data": {
            "features": {
                "combat": {
                    "aimbot": {"on": True, "fov": 90, "smooth": 3, "silent": True, "bone": "head", "key": 6},
                    "fakeHeadshot": {
                        "on": True, "visualOnly": True, "serverSeesOriginal": True,
                        "bodyToHSRate": 65, "showGoldMarker": True, "playHSSound": True,
                        "victimSeesHS": True, "maxPerMatch": 28, "burstLimit": 6
                    },
                    "noRecoil": True,
                    "noSpread": True
                },
                "esp": {
                    "on": True, "maxDist": 300, "box": True, "boxColor": "#FF0000AA",
                    "skeleton": False, "healthBar": True, "nameTag": True,
                    "distanceText": True, "lineOfSight": True,
                    "visibleColor": "#00FF00DC", "hiddenColor": "#FF505064",
                    "itemEsp": True, "itemRadius": 80, "vehicleEsp": False, "antennaHead": True
                },
                "player": {
                    "speedMult": 1.07, "jumpMult": 1.25, "noFallDmg": True, "flyMode": False
                },
                "safety": {
                    "ssCleaner": True,
                    "statsCloak": {"kdMax": 8.5, "hsRatioMax": 42, "dailyKillsMax": 38, "accMax": 68},
                    "shadowAutoOn": True, "reportBlock": True
                }
            },
            "misc": {
                "menuName": "[ O N Y X ]",
                "menuColor": [0, 255, 100],
                "floatingBtn": True,
                "btnPos": "top_right",
                "hotkey": "volume_up",
                "version": "4.1"
            },
            "guest": {
                "resetEnabled": True,
                "resetEndpoint": "/api/guest_reset",
                "regEndpoint": "/api/guest_register",
                "currentIdentity": None
            }
        },
        "flags": {
            "allEnabled": True, "safeMode": False, "updateAvailable": False,
            "banned": False, "maintainence": False
        },
        "antiDetect": {
            "rotateHWIDEachSession": True, "jitterPacketTiming": True,
            "humanizeAimInput": True, "spoofScreenshot": True, "cloakStatsBeforeSubmit": True
        }
    }
    
    if gid and gid in guest_sys.guests:
        g = guest_sys.guests[gid]
        resp['data']['guest']['currentIdentity'] = {
            'gid': gid, 'hwid': g['hwid'],
            'brand': g['device_brand'], 'model': g['device_model']
        }
    
    return jsonify(resp)

@app.route('/api/guest_register', methods=['POST'])
@app.route('/ff/guest_register', methods=['POST'])
def guest_register():
    ident = guest_sys.register()
    return jsonify({
        "code": 200, "msg": "OK",
        "data": {
            "guestId": ident['guest_id'],
            "hwid": ident['hwid'],
            "androidId": ident['android_id'],
            "advertisingId": ident['advertising_id'],
            "macAddress": ident['mac_address'],
            "imei": ident['imei'],
            "serial": ident['serial'],
            "deviceBrand": ident['device_brand'],
            "deviceModel": ident['device_model'],
            "androidVersion": ident['android_ver']
        }
    })

@app.route('/api/guest_reset', methods=['POST'])
@app.route('/ff/guest_reset', methods=['POST'])
def guest_reset():
    data = request.get_json() or {}
    old_gid = data.get('guestId') or data.get('guest_id') or data.get('gid', '')
    result = guest_sys.reset(old_gid)
    ni = result['new_identity']
    return jsonify({
        "code": 200, "msg": "RESET_SUCCESS",
        "data": {
            "oldGuestAbandoned": result['old_abandoned'],
            "newGuestId": ni['guest_id'],
            "newHwid": ni['hwid'],
            "newAndroidId": ni['android_id'],
            "newMacAddress": ni['mac_address'],
            "newDeviceBrand": ni['device_brand'],
            "newDeviceModel": ni['device_model'],
            "newImei": ni['imei'],
            "_note": "Update HWID in localconfig.json then restart game"
        }
    })

@app.route('/ping')
def ping():
    return jsonify({"status": "awake", "ts": time.time()})

@app.route('/health')
def health():
    return jsonify({"ok": True, "svc": "onyx_ff_v4", "g": len(guest_sys.guests)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("ONYX v4 starting on port", port)
    app.run(host='0.0.0.0', port=port)

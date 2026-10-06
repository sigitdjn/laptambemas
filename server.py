import os, sqlite3, json, secrets, hashlib, hmac, time, csv, io
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
ROOT = Path(__file__).parent
DATA = Path(os.environ.get('DATA_DIR', ROOT / '.data'))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'finance.sqlite3'
def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c
def init():
    with connect() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), expires REAL);
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY, project_id INTEGER REFERENCES projects(id), kind TEXT NOT NULL, date TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), party TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '', settled INTEGER NOT NULL DEFAULT 0, created_by INTEGER REFERENCES users(id));''')
        if not c.execute('SELECT 1 FROM projects').fetchone(): c.execute('INSERT INTO projects(name) VALUES(?)', ('Proyek Utama',))
def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 260000).hex()
class Handler(BaseHTTPRequestHandler):
    def reply(self, data, code=200, cookie=None):
        raw=json.dumps(data).encode(); self.send_response(code)
        self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(raw)
    def user(self,c):
        jar=SimpleCookie(); jar.load(self.headers.get('Cookie',''))
        token=jar.get('session')
        return c.execute('SELECT users.* FROM users JOIN sessions ON users.id=sessions.user_id WHERE token=? AND expires>?',(token.value if token else '',time.time())).fetchone()
    def do_GET(self):
        if self.path.startswith('/api/'):
            with connect() as c:
                u=self.user(c)
                if self.path=='/api/me': return self.reply({'user':dict(u) | {'password':None} if u else None, 'setup':not c.execute('SELECT 1 FROM users').fetchone()})
                if not u: return self.reply({'error':'Silakan login.'},401)
                if self.path=='/api/data': return self.reply({'projects':[dict(r) for r in c.execute('SELECT * FROM projects')], 'entries':[dict(r) for r in c.execute('SELECT * FROM entries ORDER BY date DESC,id DESC')], 'users':[{'name':r['name'],'email':r['email'],'role':r['role']} for r in c.execute('SELECT * FROM users')]})
            return self.reply({'error':'Tidak ditemukan'},404)
        path={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(self.path)
        if not path: return self.reply({'error':'Tidak ditemukan'},404)
        raw=(ROOT/'static'/path).read_bytes(); self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[path.split('.')[-1]])
        self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        try:
            if self.headers.get('Origin') and self.headers['Origin'].split('://',1)[-1]!=self.headers.get('Host'): return self.reply({'error':'Origin tidak diizinkan'},403)
            size=int(self.headers.get('Content-Length',0))
            if size>20000: return self.reply({'error':'Data terlalu besar'},413)
            d=json.loads(self.rfile.read(size))
            with connect() as c:
                u=self.user(c)
                if self.path in ['/api/setup','/api/users']:
                    # Serialize first-admin creation to prevent concurrent takeover.
                    c.execute('BEGIN IMMEDIATE')
                    exists=c.execute('SELECT 1 FROM users').fetchone()
                    if self.path=='/api/setup' and exists: return self.reply({'error':'Admin sudah dibuat'},403)
                    if self.path=='/api/users' and (not u or u['role']!='admin'): return self.reply({'error':'Hanya admin dapat menambah tim'},403)
                    if len(d['password'])<10 or '@' not in d['email'] or not d['name'].strip(): raise ValueError('Isi nama, email valid, dan password minimal 10 karakter.')
                    c.execute('INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)',(d['name'].strip(),d['email'].strip().lower(),password_hash(d['password']),'admin' if self.path=='/api/setup' else 'member'))
                    return self.reply({'ok':True})
                if self.path=='/api/login':
                    r=c.execute('SELECT * FROM users WHERE email=?',(d['email'].strip().lower(),)).fetchone()
                    if not r or not hmac.compare_digest(r['password'],password_hash(d['password'],r['password'].split(':')[0])): return self.reply({'error':'Email atau password salah'},401)
                    token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,r['id'],time.time()+86400))
                    return self.reply({'ok':True},cookie=f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'+ ('; Secure' if os.environ.get('COOKIE_SECURE')=='1' else ''))
                if not u: return self.reply({'error':'Silakan login'},401)
                if self.path=='/api/logout':
                    jar=SimpleCookie(); jar.load(self.headers.get('Cookie','')); c.execute('DELETE FROM sessions WHERE token=?',(jar['session'].value,))
                    return self.reply({'ok':True},cookie='session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if self.path=='/api/projects':
                    if not d['name'].strip(): raise ValueError('Nama proyek wajib diisi')
                    c.execute('INSERT INTO projects(name) VALUES(?)',(d['name'].strip(),))
                elif self.path=='/api/entries':
                    from datetime import date
                    if d['kind'] not in ['income','expense','debt','receivable','asset']: raise ValueError('Jenis tidak valid')
                    date.fromisoformat(d['date'])
                    if d.get('due'): date.fromisoformat(d['due'])
                    if not d['description'].strip() or isinstance(d['amount'],bool) or int(d['amount'])!=d['amount'] or d['amount']<=0: raise ValueError('Keterangan dan nominal rupiah positif wajib diisi')
                    c.execute('INSERT INTO entries(project_id,kind,date,description,category,amount,party,due,created_by) VALUES(?,?,?,?,?,?,?,?,?)',(d['project_id'],d['kind'],d['date'],d['description'].strip(),d['category'],d['amount'],d.get('party',''),d.get('due',''),u['id']))
                elif self.path=='/api/settle':
                    r=c.execute('SELECT * FROM entries WHERE id=?',(d['id'],)).fetchone()
                    if not r or r['kind'] not in ['debt','receivable'] or r['settled']: raise ValueError('Catatan sudah lunas atau tidak valid')
                    from datetime import date
                    c.execute('UPDATE entries SET settled=1 WHERE id=?',(r['id'],))
                    c.execute('INSERT INTO entries(project_id,kind,date,description,category,amount,party,created_by) VALUES(?,?,?,?,?,?,?,?)',(r['project_id'],'expense' if r['kind']=='debt' else 'income',date.today().isoformat(),'Pelunasan: '+r['description'],'Pelunasan',r['amount'],r['party'],u['id']))
                else: return self.reply({'error':'Tidak ditemukan'},404)
                return self.reply({'ok':True})
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as e:
            self.reply({'error':'Data tidak valid atau email sudah terdaftar.' if isinstance(e,sqlite3.IntegrityError) else str(e)},400)
if __name__=='__main__':
    init(); ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()

"""Curio's small local HTTP and SQLite backend."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('CURIO_DB', ROOT / 'curio.sqlite3'))
SUBJECTS = [('science','Science'),('history','History'),('math','Mathematics'),('nature','Nature'),('language','Language'),('art','Art & culture'),('technology','Technology'),('psychology','Psychology'),('space','Space')]

def connect():
    db=sqlite3.connect(DB_PATH)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects(id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS user_subjects(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, subject_id TEXT NOT NULL REFERENCES subjects(id), PRIMARY KEY(user_id,subject_id));
        CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES subjects(id), title TEXT NOT NULL, content_json TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'curated');
        CREATE TABLE IF NOT EXISTS completions(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, lesson_id TEXT NOT NULL, title TEXT NOT NULL, subject_id TEXT NOT NULL, completed_at TEXT NOT NULL, PRIMARY KEY(user_id,lesson_id));
        CREATE TABLE IF NOT EXISTS notification_preferences(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, enabled INTEGER NOT NULL DEFAULT 0, reminder_time TEXT NOT NULL DEFAULT '09:00');
        CREATE TABLE IF NOT EXISTS user_custom_lessons(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, lesson_id TEXT NOT NULL, subject_id TEXT NOT NULL, content_json TEXT NOT NULL, PRIMARY KEY(user_id,lesson_id));
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at TEXT NOT NULL);
        ''')
        db.executemany('INSERT OR IGNORE INTO subjects(id,name) VALUES (?,?)',SUBJECTS)

def password_hash(password, salt=None):
    salt=salt or secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000)
    return salt.hex()+':'+digest.hex()

def verify_password(password, encoded):
    try:
        salt, expected=encoded.split(':',1)
        return hmac.compare_digest(password_hash(password,bytes.fromhex(salt)).split(':',1)[1],expected)
    except (ValueError,TypeError): return False

def token_digest(token): return hashlib.sha256(token.encode()).hexdigest()

def user_state(db, user_id):
    user=db.execute('SELECT id,name,email FROM users WHERE id=?',(user_id,)).fetchone()
    interests=[r['subject_id'] for r in db.execute('SELECT subject_id FROM user_subjects WHERE user_id=? ORDER BY subject_id',(user_id,))]
    completed=[dict(id=r['lesson_id'],title=r['title'],subject=r['subject_id'],date=r['completed_at']) for r in db.execute('SELECT lesson_id,title,subject_id,completed_at FROM completions WHERE user_id=? ORDER BY completed_at',(user_id,))]
    pref=db.execute('SELECT enabled,reminder_time FROM notification_preferences WHERE user_id=?',(user_id,)).fetchone()
    custom=[]
    for r in db.execute('SELECT content_json FROM user_custom_lessons WHERE user_id=?',(user_id,)):
        try: custom.append(json.loads(r['content_json']))
        except json.JSONDecodeError: pass
    return {'user':dict(user),'state':{'name':user['name'],'email':user['email'],'subjects':interests,'completed':completed,'notification':bool(pref['enabled']) if pref else False,'notifyTime':pref['reminder_time'] if pref else '09:00','lastLearned':completed[-1]['date'] if completed else None,'lessonCount':len(completed),'customLessons':custom}}

def create_session(db,user_id):
    token=secrets.token_urlsafe(32)
    expiry=(datetime.now(timezone.utc).timestamp()+60*60*24*30)
    expires=datetime.fromtimestamp(expiry,timezone.utc).isoformat()
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)',(token_digest(token),user_id,expires))
    return token

class Handler(BaseHTTPRequestHandler):
    server_version='Curio/0.1'
    def log_message(self,fmt,*args): print('%s - %s' %(self.address_string(),fmt%args))
    def send_json(self,status,payload,headers=None):
        raw=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        except (ValueError,json.JSONDecodeError): return None
    def current_user(self,db):
        cookie=self.headers.get('Cookie','')
        token=next((p.strip()[6:] for p in cookie.split(';') if p.strip().startswith('curio=')),None)
        if not token:return None
        row=db.execute('SELECT users.id FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?',(token_digest(token),datetime.now(timezone.utc).isoformat())).fetchone()
        return row['id'] if row else None
    def do_GET(self):
        path=urlparse(self.path).path
        if path.startswith('/api/'):
            with connect() as db:
                uid=self.current_user(db)
                if not uid:return self.send_json(401,{'error':'Please sign in.'})
                if path=='/api/me' or path=='/api/state': return self.send_json(200,user_state(db,uid))
            return self.send_json(404,{'error':'Not found.'})
        return self.static_file(path)
    def do_POST(self):
        path=urlparse(self.path).path; data=self.body()
        if not isinstance(data,dict): return self.send_json(400,{'error':'Invalid request body.'})
        if path in ('/api/register','/api/login'):
            email=str(data.get('email','')).strip().lower();password=str(data.get('password',''));name=str(data.get('name','Curious learner')).strip()[:80] or 'Curious learner'
            if not email or '@' not in email or len(email)>254:return self.send_json(400,{'error':'Enter a valid email address.'})
            if path=='/api/register' and len(password)<8:return self.send_json(400,{'error':'Use a password with at least 8 characters.'})
            with connect() as db:
                if path=='/api/register':
                    try:
                        cur=db.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES (?,?,?,?)',(name,email,password_hash(password),datetime.now(timezone.utc).isoformat()));uid=cur.lastrowid
                        db.execute('INSERT INTO notification_preferences(user_id) VALUES (?)',(uid,))
                        db.executemany('INSERT INTO user_subjects(user_id,subject_id) VALUES (?,?)',[(uid,x) for x in ('science','history','math','nature')])
                    except sqlite3.IntegrityError:return self.send_json(409,{'error':'An account with that email already exists.'})
                else:
                    row=db.execute('SELECT id,password_hash FROM users WHERE email=?',(email,)).fetchone()
                    if not row or not verify_password(password,row['password_hash']):return self.send_json(401,{'error':'Email or password is incorrect.'})
                    uid=row['id']
                token=create_session(db,uid);result=user_state(db,uid)
            return self.send_json(200,result,{'Set-Cookie':f'curio={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000'})
        if path=='/api/logout':
            with connect() as db:
                cookie=self.headers.get('Cookie','');token=next((p.strip()[6:] for p in cookie.split(';') if p.strip().startswith('curio=')),None)
                if token:db.execute('DELETE FROM sessions WHERE token_hash=?',(token_digest(token),))
            return self.send_json(200,{'ok':True},{'Set-Cookie':'curio=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'})
        if path=='/api/state':
            with connect() as db:
                uid=self.current_user(db)
                if not uid:return self.send_json(401,{'error':'Please sign in.'})
                name=str(data.get('name','Curious learner')).strip()[:80] or 'Curious learner';db.execute('UPDATE users SET name=? WHERE id=?',(name,uid))
                allowed={x[0] for x in SUBJECTS};picked=list(dict.fromkeys(x for x in data.get('subjects',[]) if x in allowed)) if isinstance(data.get('subjects'),list) else []
                db.execute('DELETE FROM user_subjects WHERE user_id=?',(uid,));db.executemany('INSERT INTO user_subjects(user_id,subject_id) VALUES (?,?)',[(uid,x) for x in picked])
                custom=data.get('customLessons',[]) if isinstance(data.get('customLessons'),list) else []
                for lesson in custom:
                    try:
                        sub=lesson['subject'];lid=str(lesson['id'])
                        if sub in allowed and lid.startswith('prompt-'):db.execute('INSERT OR REPLACE INTO user_custom_lessons(user_id,lesson_id,subject_id,content_json) VALUES (?,?,?,?)',(uid,lid,sub,json.dumps(lesson,ensure_ascii=False)))
                    except (KeyError,TypeError):pass
                for item in data.get('completed',[]) if isinstance(data.get('completed'),list) else []:
                    try:
                        lid=str(item['id']);title=str(item['title'])[:200];sub=item['subject'];date=str(item['date'])
                        if sub in allowed:db.execute('INSERT OR REPLACE INTO completions(user_id,lesson_id,title,subject_id,completed_at) VALUES (?,?,?,?,?)',(uid,lid,title,sub,date))
                    except (KeyError,TypeError):pass
                db.execute('INSERT OR REPLACE INTO notification_preferences(user_id,enabled,reminder_time) VALUES (?,?,?)',(uid,int(bool(data.get('notification'))),str(data.get('notifyTime','09:00'))[:5]))
            return self.send_json(200,{'ok':True})
        return self.send_json(404,{'error':'Not found.'})
    def static_file(self,path):
        from mimetypes import guess_type
        target=(ROOT / ('index.html' if path=='/' else path.lstrip('/'))).resolve()
        if ROOT not in target.parents and target!=ROOT:return self.send_json(403,{'error':'Forbidden.'})
        if not target.is_file():return self.send_json(404,{'error':'Not found.'})
        raw=target.read_bytes();self.send_response(200);self.send_header('Content-Type',(guess_type(target.name)[0] or 'application/octet-stream')+'; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

def main():
    initialize();host=os.environ.get('CURIO_HOST','127.0.0.1');port=int(os.environ.get('CURIO_PORT','8000'))
    print(f'Curio is running at http://{host}:{port}  (SQLite: {DB_PATH})')
    try:ThreadingHTTPServer((host,port),Handler).serve_forever()
    except KeyboardInterrupt:print('\nCurio stopped.')
if __name__=='__main__':main()

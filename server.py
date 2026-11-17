"""HTTP API and SQLite persistence for Crumb."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
WEB = ROOT / 'frontend'
DB_PATH = Path(os.environ.get('CRUMB_DB', ROOT / 'crumb.sqlite3'))
SUBJECTS = [
 {'id':'biology','name':'Biology','icon':'🧬','description':'Living systems'},
 {'id':'chemistry','name':'Chemistry','icon':'⚗️','description':'Matter and reactions'},
 {'id':'physics','name':'Physics','icon':'🌌','description':'Forces and energy'},
 {'id':'math','name':'Mathematics','icon':'📐','description':'Numbers and patterns'},
 {'id':'history','name':'History','icon':'🏺','description':'People and events'},
 {'id':'geography','name':'Geography','icon':'🌍','description':'Places and landscapes'},
 {'id':'literature','name':'Literature','icon':'📚','description':'Stories and reading'},
 {'id':'language','name':'Language','icon':'🔤','description':'Words and grammar'},
 {'id':'philosophy','name':'Philosophy','icon':'💭','description':'Ideas and reasoning'},
 {'id':'economics','name':'Economics','icon':'📈','description':'Markets and choices'},
 {'id':'civics','name':'Civics','icon':'🏛️','description':'Government and society'},
 {'id':'environment','name':'Environment','icon':'🌱','description':'Ecology and climate'},
 {'id':'health','name':'Health','icon':'🫀','description':'Health and wellbeing'},
 {'id':'astronomy','name':'Astronomy','icon':'🪐','description':'Space and the universe'},
 {'id':'art','name':'Art','icon':'🎨','description':'Art and visual culture'},
 {'id':'music','name':'Music','icon':'🎵','description':'Sound and music'},
 {'id':'design','name':'Design','icon':'✏️','description':'Visual and product design'},
 {'id':'psychology','name':'Psychology','icon':'🧠','description':'Mind and behavior'},
 {'id':'computer-science','name':'Computer science','icon':'💻','description':'Computing and networks'},
 {'id':'writing','name':'Writing','icon':'✍️','description':'Clearer writing'}]
SUBJECT_MAP={x['id']:x for x in SUBJECTS}
LEGACY={'science':'biology','nature':'environment','technology':'computer-science','space':'astronomy'}
TOPIC_LENSES=(
 {'label':'overlooked object history','guidance':'Trace how one ordinary object developed over time, including a specific design change, inventor, trade, or manufacturing shift.'},
 {'label':'everyday manufacturing process','guidance':'Explain a concrete sequence of materials and manufacturing steps behind a familiar object.'},
 {'label':'material or flavor origins','guidance':'Follow a specific compound from its natural or industrial source through extraction, processing, and use.'},
 {'label':'hidden mechanism or failure mode','guidance':'Explain a non-obvious mechanism, constraint, failure, or workaround in a familiar system.'},
 {'label':'interface dark pattern','guidance':'Analyze a specific interface tactic, how it steers user behavior, and the design choice that creates it.'},
 {'label':'uncommon algorithm or data structure','guidance':'Explain a less commonly taught algorithm or data structure through its tradeoffs and a concrete use case.'},
 {'label':'niche cross-disciplinary connection','guidance':'Connect two fields through one specific object, process, technique, or historical event.'},
)
TOPIC_COUNT=10
MIN_TOPIC_COUNT=3

def connect():
    db=sqlite3.connect(DB_PATH,timeout=15)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE COLLATE NOCASE,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS subjects(id TEXT PRIMARY KEY,name TEXT NOT NULL,icon TEXT NOT NULL DEFAULT '📘',description TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS user_subjects(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,subject_id TEXT NOT NULL REFERENCES subjects(id),PRIMARY KEY(user_id,subject_id));
        CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY,subject_id TEXT NOT NULL REFERENCES subjects(id),title TEXT NOT NULL,content_json TEXT NOT NULL,source TEXT NOT NULL DEFAULT 'curated');
        CREATE TABLE IF NOT EXISTS completions(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,lesson_id TEXT NOT NULL,title TEXT NOT NULL,subject_id TEXT NOT NULL,completed_at TEXT NOT NULL,PRIMARY KEY(user_id,lesson_id));
        CREATE TABLE IF NOT EXISTS notification_preferences(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,enabled INTEGER NOT NULL DEFAULT 0,reminder_time TEXT NOT NULL DEFAULT '09:00');
        CREATE TABLE IF NOT EXISTS user_custom_lessons(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,lesson_id TEXT NOT NULL,subject_id TEXT NOT NULL,content_json TEXT NOT NULL,PRIMARY KEY(user_id,lesson_id));
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at TEXT NOT NULL);
        ''')
        columns={row['name'] for row in db.execute('PRAGMA table_info(subjects)')}
        if 'icon' not in columns:db.execute("ALTER TABLE subjects ADD COLUMN icon TEXT NOT NULL DEFAULT '📘'")
        if 'description' not in columns:db.execute("ALTER TABLE subjects ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        db.executemany('INSERT INTO subjects(id,name,icon,description) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,icon=excluded.icon,description=excluded.description',[(s['id'],s['name'],s['icon'],s['description']) for s in SUBJECTS])
        migrate_legacy_interests(db)
        for lesson in json.loads((ROOT/'data'/'lessons.json').read_text(encoding='utf-8-sig')):
            db.execute('INSERT INTO lessons(id,subject_id,title,content_json,source) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET subject_id=excluded.subject_id,title=excluded.title,content_json=excluded.content_json,source=excluded.source',(lesson['id'],lesson['subject'],lesson['title'],json.dumps(lesson,ensure_ascii=False),'curated'))

def migrate_legacy_interests(db):
    for old,new in LEGACY.items():
        db.execute('INSERT OR IGNORE INTO user_subjects(user_id,subject_id) SELECT user_id,? FROM user_subjects WHERE subject_id=?',(new,old))
        db.execute('UPDATE completions SET subject_id=? WHERE subject_id=?',(new,old))
        db.execute('UPDATE user_custom_lessons SET subject_id=? WHERE subject_id=?',(new,old))
        db.execute('DELETE FROM user_subjects WHERE subject_id=?',(old,))
        db.execute('DELETE FROM lessons WHERE subject_id=? AND source=?',(old,'curated'))

def password_hash(password,salt=None):
    salt=salt or secrets.token_bytes(16)
    return salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt,310000).hex()

def verify_password(password,encoded):
    try:
        salt,digest=encoded.split(':',1)
        return hmac.compare_digest(password_hash(password,bytes.fromhex(salt)).split(':',1)[1],digest)
    except (ValueError,TypeError): return False

def token_digest(token): return hashlib.sha256(token.encode()).hexdigest()
def now_iso(): return datetime.now(timezone.utc).isoformat()
def safe_lesson(row):
    lesson=json.loads(row['content_json'])
    lesson['id']=row['id'];lesson['subject']=row['subject_id'];lesson.setdefault('source',row['source'])
    return lesson

def account_data(db,user_id):
    user=db.execute('SELECT id,name,email FROM users WHERE id=?',(user_id,)).fetchone()
    interests=[r['subject_id'] for r in db.execute('SELECT subject_id FROM user_subjects WHERE user_id=? ORDER BY subject_id',(user_id,))]
    pref=db.execute('SELECT enabled,reminder_time FROM notification_preferences WHERE user_id=?',(user_id,)).fetchone()
    return {'user':dict(user),'preferences':{'name':user['name'],'subjects':interests,'reminderEnabled':bool(pref['enabled']) if pref else False,'reminderTime':pref['reminder_time'] if pref else '09:00'}}

def create_session(db,user_id):
    token=secrets.token_urlsafe(32);expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)',(token_digest(token),user_id,expires))
    return token
class Handler(BaseHTTPRequestHandler):
    server_version='Crumb/1.0'
    def log_message(self,fmt,*args): print('%s %s'%(self.address_string(),fmt%args))
    def send_json(self,status,payload,headers=None):
        raw=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
        for key,value in (headers or {}).items():self.send_header(key,value)
        self.end_headers();self.wfile.write(raw)
    def body(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>100_000:return None
            return json.loads(self.rfile.read(size))
        except (ValueError,json.JSONDecodeError):return None
    def current_user(self,db):
        token=next((item.strip()[6:] for item in self.headers.get('Cookie','').split(';') if item.strip().startswith('crumb=')),None)
        if not token:return None
        row=db.execute('SELECT user_id FROM sessions WHERE token_hash=? AND expires_at>?',(token_digest(token),now_iso())).fetchone()
        return row['user_id'] if row else None
    def require_user(self,db):
        uid=self.current_user(db)
        if not uid:self.send_json(401,{'error':'Sign in to continue.'})
        return uid
    def do_GET(self):
        parsed=urlparse(self.path);path=unquote(parsed.path);query=parse_qs(parsed.query)
        if path.startswith('/api/'):
            with connect() as db:
                if path=='/api/subjects':
                    rows=db.execute('SELECT id,name,icon,description FROM subjects ORDER BY name').fetchall()
                    return self.send_json(200,{'subjects':[dict(row) for row in rows if row['id'] in SUBJECT_MAP]})
                if path=='/api/lessons':
                    uid=self.current_user(db);subject=query.get('subject',[None])[0];search=query.get('q',[''])[0].strip().lower()
                    rows=db.execute('SELECT id,subject_id,content_json,source FROM lessons ORDER BY title').fetchall()
                    found=[safe_lesson(r) for r in rows if (not subject or r['subject_id']==subject) and (not search or search in r['title'].lower() or search in r['content_json'].lower())]
                    if uid:
                        customs=db.execute('SELECT lesson_id AS id,subject_id,content_json,\'generated\' AS source FROM user_custom_lessons WHERE user_id=? ORDER BY rowid DESC',(uid,)).fetchall()
                        found.extend(safe_lesson(r) for r in customs if (not subject or r['subject_id']==subject) and (not search or search in r['content_json'].lower()))
                    return self.send_json(200,{'lessons':found})
                if path=='/api/lessons/random':
                    uid=self.require_user(db)
                    if not uid:return
                    interests=[r['subject_id'] for r in db.execute('SELECT subject_id FROM user_subjects WHERE user_id=?',(uid,))]
                    if not interests:return self.send_json(200,{'lesson':None})
                    done={r['lesson_id'] for r in db.execute('SELECT lesson_id FROM completions WHERE user_id=?',(uid,))}
                    rows=db.execute('SELECT id,subject_id,content_json,source FROM lessons WHERE subject_id IN ('+','.join('?' for _ in interests)+')',interests).fetchall()
                    choices=[r for r in rows if r['id'] not in done]
                    if not choices:choices=rows
                    import random
                    return self.send_json(200,{'lesson':safe_lesson(random.choice(choices)) if choices else None})
                if path.startswith('/api/lessons/'):
                    lesson_id=path.removeprefix('/api/lessons/')
                    row=db.execute('SELECT id,subject_id,content_json,source FROM lessons WHERE id=?',(lesson_id,)).fetchone()
                    if row:return self.send_json(200,{'lesson':safe_lesson(row)})
                    uid=self.current_user(db)
                    if uid:
                        row=db.execute('SELECT lesson_id AS id,subject_id,content_json,\'generated\' AS source FROM user_custom_lessons WHERE user_id=? AND lesson_id=?',(uid,lesson_id)).fetchone()
                        if row:return self.send_json(200,{'lesson':safe_lesson(row)})
                    return self.send_json(404,{'error':'Lesson not found.'})
                uid=self.require_user(db)
                if not uid:return
                if path in ('/api/me','/api/preferences'):return self.send_json(200,account_data(db,uid))
                if path=='/api/progress':
                    rows=db.execute('SELECT lesson_id,title,subject_id,completed_at FROM completions WHERE user_id=? ORDER BY completed_at DESC',(uid,)).fetchall()
                    days={datetime.fromisoformat(r['completed_at']).date() for r in rows};today=datetime.now(timezone.utc).date();cursor=today if today in days else today-timedelta(days=1);streak=0
                    while cursor in days:streak+=1;cursor-=timedelta(days=1)
                    return self.send_json(200,{'completed':[dict(id=r['lesson_id'],title=r['title'],subject=r['subject_id'],date=r['completed_at']) for r in rows],'lessonsCompleted':len(rows),'streak':streak,'completedToday':sum(datetime.fromisoformat(r['completed_at']).date()==today for r in rows)})
            return self.send_json(404,{'error':'Route not found.'})
        return self.static_file(path)
    def do_POST(self):
        path=unquote(urlparse(self.path).path);data=self.body()
        if not isinstance(data,dict):return self.send_json(400,{'error':'Invalid request body.'})
        if path in ('/api/register','/api/login'):
            return self.authenticate(path,data)
        if path=='/api/logout':
            with connect() as db:
                token=next((x.strip()[6:] for x in self.headers.get('Cookie','').split(';') if x.strip().startswith('crumb=')),None)
                if token:db.execute('DELETE FROM sessions WHERE token_hash=?',(token_digest(token),))
            return self.send_json(200,{'ok':True},{'Set-Cookie':'crumb=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'})
        with connect() as db:
            uid=self.require_user(db)
            if not uid:return
            if path=='/api/preferences':return self.save_preferences(db,uid,data)
            if path=='/api/completions':return self.complete_lesson(db,uid,data)
            if path=='/api/lessons/generate':return self.generate_lesson(db,uid,data)
        return self.send_json(404,{'error':'Route not found.'})
    def do_PUT(self):
        self.do_POST()
    def authenticate(self,path,data):
        email=str(data.get('email','')).strip().lower();password=str(data.get('password',''));name=str(data.get('name','')).strip()[:80] or 'Learner'
        if not email or '@' not in email or len(email)>254:return self.send_json(400,{'error':'Enter a valid email address.'})
        if path=='/api/register' and len(password)<8:return self.send_json(400,{'error':'Password must have at least 8 characters.'})
        with connect() as db:
            if path=='/api/register':
                try:
                    cur=db.execute('INSERT INTO users(name,email,password_hash,created_at) VALUES (?,?,?,?)',(name,email,password_hash(password),now_iso()));uid=cur.lastrowid
                    db.execute('INSERT INTO notification_preferences(user_id) VALUES (?)',(uid,))
                except sqlite3.IntegrityError:return self.send_json(409,{'error':'An account with this email already exists.'})
            else:
                row=db.execute('SELECT id,password_hash FROM users WHERE email=?',(email,)).fetchone()
                if not row or not verify_password(password,row['password_hash']):return self.send_json(401,{'error':'Email or password is incorrect.'})
                uid=row['id']
            token=create_session(db,uid);result=account_data(db,uid)
        return self.send_json(200,result,{'Set-Cookie':f'crumb={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000'})
    def save_preferences(self,db,uid,data):
        name=str(data.get('name','Learner')).strip()[:80] or 'Learner'
        interests=data.get('subjects',[])
        if not isinstance(interests,list):return self.send_json(400,{'error':'Subjects must be a list.'})
        selected=list(dict.fromkeys(x for x in interests if x in SUBJECT_MAP))
        time=str(data.get('reminderTime','09:00'))
        if len(time)!=5 or time[2]!=':' or not time[:2].isdigit() or not time[3:].isdigit() or int(time[:2])>23 or int(time[3:])>59:time='09:00'
        db.execute('UPDATE users SET name=? WHERE id=?',(name,uid))
        db.execute('DELETE FROM user_subjects WHERE user_id=?',(uid,))
        db.executemany('INSERT INTO user_subjects(user_id,subject_id) VALUES (?,?)',[(uid,sid) for sid in selected])
        db.execute('INSERT OR REPLACE INTO notification_preferences(user_id,enabled,reminder_time) VALUES (?,?,?)',(uid,int(bool(data.get('reminderEnabled'))),time))
        return self.send_json(200,account_data(db,uid))
    def complete_lesson(self,db,uid,data):
        lesson_id=str(data.get('lessonId',''))
        row=db.execute('SELECT id,subject_id,title FROM lessons WHERE id=?',(lesson_id,)).fetchone()
        if row:subject_id,title=row['subject_id'],row['title']
        else:
            row=db.execute('SELECT lesson_id,subject_id,content_json FROM user_custom_lessons WHERE user_id=? AND lesson_id=?',(uid,lesson_id)).fetchone()
            if not row:return self.send_json(404,{'error':'Lesson not found.'})
            lesson=json.loads(row['content_json']);subject_id=row['subject_id'];title=lesson['title']
        db.execute('INSERT OR IGNORE INTO completions(user_id,lesson_id,title,subject_id,completed_at) VALUES (?,?,?,?,?)',(uid,lesson_id,title,subject_id,now_iso()))
        return self.send_json(201,{'ok':True,'lessonId':lesson_id})
    def generate_gemini_json(self,api_key,model,prompt,temperature):
        payload={'contents':[{'role':'user','parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','temperature':temperature}}
        request=Request('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',data=json.dumps(payload).encode(),headers={'x-goog-api-key':api_key,'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=45) as response:api_result=json.loads(response.read())
        output=''.join(part.get('text','') for part in api_result['candidates'][0]['content']['parts'])
        return json.loads(output)
    def generate_lesson(self,db,uid,data):
        interests=[r['subject_id'] for r in db.execute('SELECT subject_id FROM user_subjects WHERE user_id=?',(uid,))]
        random_topic=bool(data.get('randomTopic'))
        available=[subject for subject in interests if subject in SUBJECT_MAP] if random_topic else []
        prompt=''
        if random_topic and not available:return self.send_json(400,{'error':'Choose at least one subject before generating a random topic.'})
        if not random_topic:
            prompt=str(data.get('prompt','')).strip()[:240]
            if len(prompt)<3:return self.send_json(400,{'error':'Enter a topic or question.'})
        api_key=os.environ.get('GEMINI_API_KEY')
        if not api_key:return self.send_json(503,{'error':'Topic generation is not configured. Set GEMINI_API_KEY on the server.'})
        model=os.environ.get('GEMINI_MODEL') or 'gemini-3.5-flash-lite'
        selected_subject=None
        if random_topic:
            selected_subject=secrets.choice(available)
            lens=secrets.choice(TOPIC_LENSES)
            topic_prompt=(f'Generate exactly {TOPIC_COUNT} distinct, accurate microlearning lesson topics for the subject {selected_subject} ({SUBJECT_MAP[selected_subject]["name"]}). '
                f'Topic lens: {lens["label"]}. {lens["guidance"]} '
                'Aim for unusually specific, niche micro-lessons rather than entry-level or commonly repeated topics. Avoid broad introductions, textbook overviews, and generic "what is X" questions. '
                'Use these as specificity calibration only; do not copy or closely paraphrase them: the history of the shoelace; how a pencil eraser is made step by step; dark patterns in UI; where common flavor compounds come from; rope data structures. '
                'Each candidate should name a particular object, process, mechanism, compound, interface tactic, algorithm, or historical detail, and should be accurate and researchable rather than obscure by invention. '
                'Return only a JSON object with a "topics" array of objects, each containing topic (5-160 characters), lens (short label), and rationale (one concise sentence explaining its specificity).')
            try:topic_result=self.generate_gemini_json(api_key,model,topic_prompt,1.0)
            except (HTTPError,URLError,TimeoutError) as error:
                detail=getattr(error,'code',None)
                return self.send_json(502,{'error':f'Topic service request failed{f" ({detail})" if detail else ""}.'})
            except (ValueError,KeyError,IndexError,TypeError):return self.send_json(502,{'error':'Topic service returned an unreadable response.'})
            if not isinstance(topic_result,dict) or not isinstance(topic_result.get('topics'),list):return self.send_json(502,{'error':'Topic service returned an invalid topic list.'})
            topics=[];seen=set()
            for candidate in topic_result['topics']:
                if not isinstance(candidate,dict):continue
                topic=candidate.get('topic');label=candidate.get('lens');rationale=candidate.get('rationale')
                if not isinstance(topic,str) or not isinstance(label,str) or not label.strip() or not isinstance(rationale,str) or not rationale.strip():continue
                topic=topic.strip();normalized=topic.casefold()
                if 5<=len(topic)<=160 and normalized not in seen:
                    topics.append(topic);seen.add(normalized)
                if len(topics)==TOPIC_COUNT:break
            if len(topics)<MIN_TOPIC_COUNT:return self.send_json(502,{'error':'Topic service returned too few usable topics.'})
            prompt=secrets.choice(topics)
        subject_instruction=f'Use subject id "{selected_subject}".' if selected_subject else 'Choose the best matching subject id.'
        instruction=('Create one accurate, substantial microlearning lesson for this topic: '+prompt+'\n'+subject_instruction+' Return only a JSON object with subject (allowed id), title, tag, minutes (integer 8-12), lead, sections (exactly 5 objects, each with a concise heading and a body of 90-140 words), takeaway, questions (exactly 4 objects, each with question, options (exactly 3 strings), answerIndex (0-2), and a brief explanation), and source. Build a clear progression across sections, explain important terms with examples, and use plain language. Make the questions test different points from the lesson. If unsure, state uncertainty in the relevant section. Allowed subject ids: '+', '.join(SUBJECT_MAP))
        try:
            lesson=self.generate_gemini_json(api_key,model,instruction,0.8)
        except (HTTPError,URLError,TimeoutError) as error:
            detail=getattr(error,'code',None)
            return self.send_json(502,{'error':f'Lesson service request failed{f" ({detail})" if detail else ""}.'})
        except (ValueError,KeyError,IndexError,TypeError):return self.send_json(502,{'error':'Lesson service returned an unreadable response.'})
        if not isinstance(lesson,dict):return self.send_json(502,{'error':'Lesson service returned an invalid lesson.'})
        subject=lesson.get('subject')
        required=('title','tag','lead','takeaway')
        sections=lesson.get('sections')
        questions=lesson.get('questions')
        if subject not in SUBJECT_MAP or (selected_subject and subject!=selected_subject) or any(not isinstance(lesson.get(key),str) or not lesson[key].strip() for key in required) or not isinstance(sections,list) or not 4<=len(sections)<=7 or not isinstance(questions,list) or not 3<=len(questions)<=5:return self.send_json(502,{'error':'Lesson service returned an invalid lesson.'})
        section_words=0
        for section in sections:
            if not isinstance(section,dict) or not isinstance(section.get('heading'),str) or not section['heading'].strip() or not isinstance(section.get('body'),str) or not section['body'].strip():return self.send_json(502,{'error':'Lesson service returned invalid sections.'})
            section_words+=len(section['body'].split())
        if section_words<400:return self.send_json(502,{'error':'Lesson service returned a lesson that is too short.'})
        for question in questions:
            if not isinstance(question,dict) or not isinstance(question.get('question'),str) or not question['question'].strip() or not isinstance(question.get('options'),list) or len(question['options'])!=3 or any(not isinstance(option,str) or not option.strip() for option in question['options']) or not isinstance(question.get('answerIndex'),int) or question['answerIndex'] not in (0,1,2) or not isinstance(question.get('explanation'),str) or not question['explanation'].strip():return self.send_json(502,{'error':'Lesson service returned invalid questions.'})
        try:minutes=int(lesson.get('minutes',8))
        except (ValueError,TypeError):minutes=8
        lesson.update(id='gen-'+secrets.token_hex(10),minutes=max(8,min(minutes,12)),source='Generated lesson')
        lesson['body']=' '.join(section['body'].strip() for section in sections)
        lesson['question']=questions[0]['question']
        lesson['options']=[option[:240] for option in questions[0]['options']]
        lesson['answerIndex']=questions[0]['answerIndex']
        db.execute('INSERT INTO user_custom_lessons(user_id,lesson_id,subject_id,content_json) VALUES (?,?,?,?)',(uid,lesson['id'],subject,json.dumps(lesson,ensure_ascii=False)))
        return self.send_json(201,{'lesson':lesson})
    def static_file(self,path):
        target=(WEB/('index.html' if path=='/' else path.lstrip('/'))).resolve()
        if WEB not in target.parents:return self.send_json(403,{'error':'Forbidden.'})
        if not target.is_file():return self.send_json(404,{'error':'File not found.'})
        import mimetypes
        raw=target.read_bytes();self.send_response(200);self.send_header('Content-Type',(mimetypes.guess_type(target.name)[0] or 'application/octet-stream')+'; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

def main():
    initialize();host=os.environ.get('CRUMB_HOST','127.0.0.1');port=int(os.environ.get('CRUMB_PORT','8000'))
    print(f'Crumb: http://{host}:{port} · SQLite: {DB_PATH}')
    try:ThreadingHTTPServer((host,port),Handler).serve_forever()
    except KeyboardInterrupt:print('\nCrumb stopped.')
if __name__=='__main__':main()

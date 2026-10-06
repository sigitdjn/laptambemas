import unittest, tempfile, subprocess, os, socket, time, urllib.request, urllib.error, http.cookiejar, json
from pathlib import Path
class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        with socket.socket() as s: s.bind(('127.0.0.1',0)); cls.port=s.getsockname()[1]
        cls.proc=subprocess.Popen(['python3','server.py'],cwd=Path(__file__).resolve().parents[1],env={**os.environ,'DATA_DIR':cls.tmp.name,'PORT':str(cls.port)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cls.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        for _ in range(60):
            try: cls.call('me'); break
            except OSError: time.sleep(.1)
        else: raise RuntimeError('Server failed to start')
    @classmethod
    def tearDownClass(cls): cls.proc.terminate(); cls.proc.wait(); cls.tmp.cleanup()
    @classmethod
    def call(cls,path,data=None,client=None):
        req=urllib.request.Request(f'http://127.0.0.1:{cls.port}/api/{path}',data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
        with (client or cls.client).open(req) as r: return json.load(r)
    def test_workflow(self):
        self.assertTrue(self.call('me')['setup'])
        self.call('setup',{'name':'Admin','email':'admin@example.com','password':'test-pass-12345'})
        with self.assertRaises(urllib.error.HTTPError) as e:self.call('setup',{'name':'Other','email':'o@example.com','password':'test-pass-12345'})
        self.assertEqual(e.exception.code,403)
        self.call('login',{'email':'admin@example.com','password':'test-pass-12345'})
        base={'project_id':1,'date':'2026-10-06','category':'Modal','party':'Investor','due':'','description':'Modal','amount':1000000,'kind':'income'}
        self.call('entries',base)
        self.call('entries',{**base,'kind':'expense','amount':100000})
        self.call('entries',{**base,'kind':'debt','amount':200000})
        self.call('entries',{**base,'kind':'receivable','amount':50000})
        self.call('entries',{**base,'kind':'asset','amount':300000})
        d=self.call('data'); debt=next(e for e in d['entries'] if e['kind']=='debt'); rec=next(e for e in d['entries'] if e['kind']=='receivable')
        self.call('settle',{'id':debt['id']});self.call('settle',{'id':rec['id']})
        with self.assertRaises(urllib.error.HTTPError):self.call('settle',{'id':debt['id']})
        rows=self.call('data')['entries']; self.assertEqual(sum(e['amount']*(1 if e['kind']=='income' else -1 if e['kind']=='expense' else 0) for e in rows),750000)
        self.call('users',{'name':'Team','email':'team@example.com','password':'team-pass-12345'})
        self.call('logout',{});self.call('login',{'email':'team@example.com','password':'team-pass-12345'})
        self.assertEqual(len(self.call('data')['entries']),7)
        with self.assertRaises(urllib.error.HTTPError) as e:self.call('users',{'name':'Bad','email':'bad@example.com','password':'test-pass-12345'})
        self.assertEqual(e.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError):self.call('entries',{**base,'amount':-1})
        self.call('logout',{})
        with self.assertRaises(urllib.error.HTTPError) as e:self.call('data')
        self.assertEqual(e.exception.code,401)
        self.proc.terminate();self.proc.wait()
        self.proc=subprocess.Popen(['python3','server.py'],cwd=Path(__file__).resolve().parents[1],env={**os.environ,'DATA_DIR':self.tmp.name,'PORT':str(self.port)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        type(self).proc=self.proc
        for _ in range(60):
            try:self.call('me');break
            except OSError:time.sleep(.1)
        self.call('login',{'email':'admin@example.com','password':'test-pass-12345'})
        self.assertEqual(len(self.call('data')['entries']),7)
if __name__=='__main__':unittest.main()

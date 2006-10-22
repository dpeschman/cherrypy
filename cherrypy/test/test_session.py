from cherrypy.test import test
test.prefer_parent_path()

import os
localDir = os.path.dirname(__file__)
import sys
import threading
import time

import cherrypy
from cherrypy.lib import sessions


def setup_server():
    class Root:
        
        _cp_config = {'tools.sessions.on': True,
                      'tools.sessions.storage_type' : 'ram',
                      'tools.sessions.storage_path' : localDir,
                      'tools.sessions.timeout': 0.017,    # 1.02 secs
                      'tools.sessions.clean_freq': 0.017,
                      }
        
        def testGen(self):
            counter = cherrypy.session.get('counter', 0) + 1
            cherrypy.session['counter'] = counter
            yield str(counter)
        testGen.exposed = True
        
        def testStr(self):
            counter = cherrypy.session.get('counter', 0) + 1
            cherrypy.session['counter'] = counter
            return str(counter)
        testStr.exposed = True
        
        def setsessiontype(self, newtype):
            self.__class__._cp_config.update({'tools.sessions.storage_type': newtype})
        setsessiontype.exposed = True
        
        def index(self):
            sess = cherrypy.session
            c = sess.get('counter', 0) + 1
            time.sleep(0.01)
            sess['counter'] = c
            return str(c)
        index.exposed = True
        
        def delete(self):
            cherrypy.session.delete()
            sessions.expire()
            return "done"
        delete.exposed = True
        
        def blah(self):
            return self._cp_config['tools.sessions.storage_type']
        blah.exposed = True
        
        def iredir(self):
            raise cherrypy.InternalRedirect('/blah')
        iredir.exposed = True
    
    cherrypy.tree.mount(Root())
    cherrypy.config.update({'environment': 'test_suite'})


from cherrypy.test import helper

class SessionTest(helper.CPWebCase):
    
    def test_0_Session(self):
        self.getPage('/testStr')
        self.assertBody('1')
        self.getPage('/testGen', self.cookies)
        self.assertBody('2')
        self.getPage('/testStr', self.cookies)
        self.assertBody('3')
        
        self.getPage('/setsessiontype/file')
        self.getPage('/testStr')
        self.assertBody('1')
        self.getPage('/testGen', self.cookies)
        self.assertBody('2')
        self.getPage('/testStr', self.cookies)
        self.assertBody('3')
        
        # Wait for the session.timeout (1.02 secs)
        time.sleep(1.25)
        self.getPage('/')
        self.assertBody('1')
        
        # Test session delete
        self.getPage('/delete', self.cookies)
        self.assertBody("done")
        f = lambda: [x for x in os.listdir(localDir) if x.startswith('session-')]
        self.assertEqual(f(), [])
        
        # Wait for the cleanup thread to delete remaining session files
        self.getPage('/')
        f = lambda: [x for x in os.listdir(localDir) if x.startswith('session-')]
        self.assertNotEqual(f(), [])
        time.sleep(2)
        self.assertEqual(f(), [])
    
    def test_1_Ram_Concurrency(self):
        self.getPage('/setsessiontype/ram')
        self._test_Concurrency()
    
    def test_2_File_Concurrency(self):
        self.getPage('/setsessiontype/file')
        self._test_Concurrency()
    
    def _test_Concurrency(self):
        client_thread_count = 5
        request_count = 30
        
        # Get initial cookie
        self.getPage("/")
        self.assertBody("1")
        cookies = self.cookies
        
        data_dict = {}
        
        def request(index):
            for i in xrange(request_count):
                self.getPage("/", cookies)
                # Uncomment the following line to prove threads overlap.
##                print index,
            data_dict[index] = v = int(self.body)
        
        # Start <request_count> concurrent requests from
        # each of <client_thread_count> clients
        ts = []
        for c in xrange(client_thread_count):
            data_dict[c] = 0
            t = threading.Thread(target=request, args=(c,))
            ts.append(t)
            t.start()
        
        for t in ts:
            t.join()
        
        hitcount = max(data_dict.values())
        expected = 1 + (client_thread_count * request_count)
        self.assertEqual(hitcount, expected)
    
    def test_3_Redirect(self):
        # Start a new session
        self.getPage('/testStr')
        self.getPage('/iredir', self.cookies)
        self.assertBody("file")
    
    def test_4_File_deletion(self):
        # Start a new session
        self.getPage('/testStr')
        # Delete the session file manually and retry.
        id = self.cookies[0][1].split(";", 1)[0].split("=", 1)[1]
        path = os.path.join(localDir, "session-" + id)
        os.unlink(path)
        self.getPage('/testStr', self.cookies)



if __name__ == "__main__":
    setup_server()
    helper.testmain()

import time
import unittest
from unittest.mock import Mock, patch

from flask import Flask
import remote_web
from desktop_control import coordinate, WindowsDesktop


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__)
        self.app.secret_key='test-only'
        self.app.register_blueprint(remote_web.remote)
        self.app.testing=True
        self.client=self.app.test_client()
        self.backend=Mock()
        self.backend.capture.return_value=(b'jpeg',dict(hwnd=100,pid=200,title='ChatGPT',rect=(0,0,800,600)))
        self.mock=patch.object(remote_web,'backend',return_value=self.backend)
        self.mock.start()
        remote_web._frames.clear()

    def tearDown(self):
        self.mock.stop()
        remote_web._frames.clear()

    def frame(self):
        return self.client.post('/remote/frame',json={'window':100}).json['token']

    def test_frame_token_single_use(self):
        token=self.frame()
        data=dict(token=token,action='text',text='Salut')
        self.assertEqual(self.client.post('/remote/action',json=data).status_code,200)
        self.assertEqual(self.client.post('/remote/action',json=data).status_code,409)
        self.backend.action.assert_called_once()

    def test_other_browser_cannot_use_frame(self):
        token=self.frame()
        other=self.app.test_client()
        self.assertEqual(other.post('/remote/action',json=dict(token=token,action='click',x=.5,y=.5)).status_code,409)
        self.backend.action.assert_not_called()

    def test_expired_and_invalid_requests(self):
        token=self.frame()
        remote_web._frames[token]['time']=time.monotonic()-30
        self.assertEqual(self.client.post('/remote/action',json=dict(token=token,action='key',key='enter')).status_code,409)
        self.assertEqual(self.client.post('/remote/frame',json={'window':True}).status_code,400)
        self.assertEqual(self.client.post('/remote/frame',json=['not an object']).status_code,400)
        self.backend.action.assert_not_called()

    def test_window_rejection_is_reported(self):
        self.backend.capture.side_effect=ValueError('Only ChatGPT')
        self.assertEqual(self.client.post('/remote/frame',json={'window':999}).status_code,409)

    def test_coordinate_bounds(self):
        for value in (-.01,1.01,float('nan'),float('inf'),True,'0.5',None):
            with self.assertRaises(ValueError): coordinate(value)
        self.assertEqual(coordinate(.5),.5)

    def test_unicode_text_does_not_press_enter(self):
        desktop=WindowsDesktop.__new__(WindowsDesktop)
        desktop.validate_frame=Mock()
        desktop.send=Mock()
        desktop.action({},dict(action='text',text='Salut, țară!\n🙂'))
        events=desktop.send.call_args.args[0]
        self.assertTrue(all(kind=='unicode' for kind,_,_ in events))
        self.assertFalse(any(value in (10,13) for _,value,_ in events))
        units=b''.join(value.to_bytes(2,'little') for _,value,flags in events if flags==0)
        self.assertEqual(units.decode('utf-16-le'),'Salut, țară! 🙂')

    def test_arbitrary_keys_and_commands_are_rejected(self):
        desktop=WindowsDesktop.__new__(WindowsDesktop)
        desktop.validate_frame=Mock()
        desktop.send=Mock()
        for data in (dict(action='key',key='win+r'),dict(action='shell',text='anything'),dict(action='text',text='x'*4001)):
            with self.assertRaises(ValueError): desktop.action({},data)
        desktop.send.assert_not_called()

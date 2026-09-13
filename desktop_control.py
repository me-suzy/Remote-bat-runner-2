"""User-operated, window-scoped Windows controls. No command execution endpoint."""
import ctypes as c
from ctypes import wintypes as w
import io
import math
import threading

from PIL import Image

LOCK = threading.RLock()


def coordinate(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Coordonată invalidă.")
    return value


class WindowsDesktop:
    def __init__(self):
        self.u = c.WinDLL("user32", use_last_error=True)
        self.g = c.WinDLL("gdi32", use_last_error=True)
        self.k = c.WinDLL("kernel32", use_last_error=True)
        # Pointer-sized signatures are required on 64-bit Windows.
        signatures = [
            (self.u, 'GetWindowRect', [w.HWND, c.POINTER(w.RECT)], w.BOOL),
            (self.u, 'IsWindowVisible', [w.HWND], w.BOOL),
            (self.u, 'IsIconic', [w.HWND], w.BOOL),
            (self.u, 'GetWindowTextW', [w.HWND, w.LPWSTR, c.c_int], c.c_int),
            (self.u, 'GetWindowThreadProcessId', [w.HWND, c.POINTER(w.DWORD)], w.DWORD),
            (self.u, 'GetForegroundWindow', [], w.HWND),
            (self.u, 'SetForegroundWindow', [w.HWND], w.BOOL),
            (self.u, 'AttachThreadInput', [w.DWORD,w.DWORD,w.BOOL],w.BOOL),
            (self.u, 'ShowWindow', [w.HWND, c.c_int], w.BOOL),
            (self.u, 'WindowFromPoint', [w.POINT], w.HWND),
            (self.u, 'GetAncestor', [w.HWND, w.UINT], w.HWND),
            (self.u, 'GetWindowDC', [w.HWND], w.HDC),
            (self.u, 'ReleaseDC', [w.HWND, w.HDC], c.c_int),
            (self.u, 'PrintWindow', [w.HWND, w.HDC, w.UINT], w.BOOL),
            (self.u, 'OpenInputDesktop', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            (self.u, 'CloseDesktop', [w.HANDLE], w.BOOL),
            (self.u, 'GetUserObjectInformationW', [w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],w.BOOL),
            (self.k, 'OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            (self.k, 'QueryFullProcessImageNameW', [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)], w.BOOL),
            (self.k, 'CloseHandle', [w.HANDLE], w.BOOL),
            (self.k, 'GetCurrentThreadId', [],w.DWORD),
            (self.g, 'CreateCompatibleDC', [w.HDC], w.HDC),
            (self.g, 'CreateCompatibleBitmap', [w.HDC, c.c_int, c.c_int], w.HBITMAP),
            (self.g, 'SelectObject', [w.HDC, w.HANDLE], w.HANDLE),
            (self.g, 'DeleteObject', [w.HANDLE], w.BOOL),
            (self.g, 'DeleteDC', [w.HDC], w.BOOL),
            (self.g, 'GetDIBits', [w.HDC, w.HBITMAP, w.UINT, w.UINT, c.c_void_p, c.c_void_p, w.UINT], c.c_int),
        ]
        for lib, name, args, result in signatures:
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = args, result
        try:
            self.u.SetProcessDpiAwarenessContext(c.c_void_p(-4))
        except AttributeError:
            self.u.SetProcessDPIAware()

    def unlocked(self):
        handle = self.u.OpenInputDesktop(0, False, 0x0100)
        if not handle:
            raise ValueError("Desktopul Windows nu este disponibil. Deblochează laptopul.")
        try:
            name,needed=c.create_unicode_buffer(256),w.DWORD()
            if not self.u.GetUserObjectInformationW(handle,2,name,c.sizeof(name),c.byref(needed)) or name.value.lower() != 'default':
                raise ValueError("Desktopul Windows este blocat sau protejat. Revino la desktopul normal.")
        finally:
            self.u.CloseDesktop(handle)

    def identity(self, hwnd):
        if not self.u.IsWindowVisible(hwnd):
            raise ValueError("Fereastra nu mai este disponibilă.")
        pid = w.DWORD()
        self.u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        process = self.k.OpenProcess(0x1000, False, pid.value)
        path, length = c.create_unicode_buffer(32768), w.DWORD(32768)
        try:
            ok = process and self.k.QueryFullProcessImageNameW(process, 0, path, c.byref(length))
        finally:
            if process:
                self.k.CloseHandle(process)
        if not ok or path.value.rsplit('\\', 1)[-1].lower() != 'chatgpt.exe':
            raise ValueError("Controlul este permis doar pentru aplicația ChatGPT.")
        title = c.create_unicode_buffer(1024)
        self.u.GetWindowTextW(hwnd, title, len(title))
        return pid.value, title.value

    def windows(self):
        self.unlocked()
        result = []
        callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

        @callback_type
        def visit(hwnd, unused):
            try:
                pid, title = self.identity(hwnd)
                if title:
                    result.append(dict(id=hwnd, title=title, pid=pid))
            except ValueError:
                pass
            return True
        self.u.EnumWindows(visit, 0)
        return result

    def rect(self, hwnd):
        rect = w.RECT()
        if not self.u.GetWindowRect(hwnd, c.byref(rect)):
            raise ValueError("Fereastra nu mai este disponibilă.")
        return (rect.left, rect.top, rect.right, rect.bottom)

    def activate(self, hwnd):
        self.unlocked()
        self.identity(hwnd)
        if self.u.IsIconic(hwnd):
            self.u.ShowWindow(hwnd, 9)
        self.u.SetForegroundWindow(hwnd)
        if self.u.GetForegroundWindow() != hwnd:
            foreground_thread=self.u.GetWindowThreadProcessId(self.u.GetForegroundWindow(),None)
            this_thread=self.k.GetCurrentThreadId()
            attached=foreground_thread and foreground_thread != this_thread and self.u.AttachThreadInput(this_thread,foreground_thread,True)
            try:
                if attached:
                    self.u.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    self.u.AttachThreadInput(this_thread,foreground_thread,False)
        if self.u.GetForegroundWindow() != hwnd:
            raise ValueError("Windows nu permite activarea ferestrei. Selectează ChatGPT pe laptop sau folosește TeamViewer.")

    def capture(self, hwnd):
        self.unlocked()
        pid, title = self.identity(hwnd)
        if self.u.IsIconic(hwnd):
            raise ValueError("ChatGPT este minimizat. Apasă Activează fereastra.")
        rect = self.rect(hwnd)
        width, height = rect[2]-rect[0], rect[3]-rect[1]
        if not 1 <= width <= 10000 or not 1 <= height <= 10000:
            raise ValueError("Dimensiuni indisponibile.")
        dc = self.u.GetWindowDC(hwnd)
        mem = self.g.CreateCompatibleDC(dc)
        bitmap = self.g.CreateCompatibleBitmap(dc, width, height)
        old = self.g.SelectObject(mem, bitmap)
        try:
            if not self.u.PrintWindow(hwnd, mem, 2):
                raise ValueError("Captura ferestrei a eșuat. Folosește TeamViewer.")
            self.g.SelectObject(mem, old)
            old = None
            # BITMAPINFOHEADER: 32-bit BGRA, top-down rows.
            import struct
            info = c.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0))
            pixels = c.create_string_buffer(width*height*4)
            if not self.g.GetDIBits(mem, bitmap, 0, height, pixels, info, 0):
                raise ValueError("Nu pot citi imaginea ferestrei.")
            picture = Image.frombuffer('RGB', (width,height), pixels.raw, 'raw', 'BGRX', 0, 1)
            picture.thumbnail((1600, 1200))
            data = io.BytesIO()
            picture.save(data, format='JPEG', quality=75)
            return data.getvalue(), dict(hwnd=hwnd, pid=pid, title=title, rect=rect)
        finally:
            if old:
                self.g.SelectObject(mem, old)
            self.g.DeleteObject(bitmap)
            self.g.DeleteDC(mem)
            self.u.ReleaseDC(hwnd, dc)

    def validate_frame(self, frame):
        self.unlocked()
        pid, _ = self.identity(frame['hwnd'])
        if pid != frame['pid'] or self.rect(frame['hwnd']) != tuple(frame['rect']):
            raise ValueError("Fereastra s-a schimbat. Reîmprospătează imaginea.")
        if self.u.GetForegroundWindow() != frame['hwnd']:
            raise ValueError("ChatGPT nu este în prim-plan. Apasă Activează fereastra.")
        if any(self.u.GetAsyncKeyState(vk) & 0x8000 for vk in (16,17,18)):
            raise ValueError("O tastă Shift/Ctrl/Alt este apăsată pe laptop. Elibereaz-o înainte de comandă.")

    def send(self, events):
        class Mouse(c.Structure):
            _fields_ = [('dx',w.LONG),('dy',w.LONG),('data',w.DWORD),('flags',w.DWORD),('time',w.DWORD),('extra',c.c_size_t)]
        class Keyboard(c.Structure):
            _fields_ = [('vk',w.WORD),('scan',w.WORD),('flags',w.DWORD),('time',w.DWORD),('extra',c.c_size_t)]
        class Payload(c.Union):
            _fields_ = [('mouse',Mouse),('keyboard',Keyboard)]
        class Input(c.Structure):
            _fields_ = [('type',w.DWORD),('payload',Payload)]
        inputs = []
        for kind, value, flags in events:
            payload = Payload()
            if kind == 'unicode':
                payload.keyboard = Keyboard(0,value,flags|4,0,0)
            elif kind == 'key':
                payload.keyboard = Keyboard(value,0,flags,0,0)
            else:
                payload.mouse = Mouse(0,0,value & 0xffffffff,flags,0,0)
            inputs.append(Input(0 if kind == 'mouse' else 1, payload))
        array = (Input*len(inputs))(*inputs)
        self.u.SendInput.argtypes = [w.UINT,c.POINTER(Input),c.c_int]
        if self.u.SendInput(len(inputs),array,c.sizeof(Input)) != len(inputs):
            raise ValueError("Windows a blocat introducerea. Verifică textul înainte de a încerca din nou.")

    def action(self, frame, payload):
        self.validate_frame(frame)
        action = payload.get('action')
        if action == 'click':
            x,y = coordinate(payload.get('x')),coordinate(payload.get('y'))
            left,top,right,bottom=frame['rect']
            point=w.POINT(left+int(x*(right-left-1)), top+int(y*(bottom-top-1)))
            hit=self.u.WindowFromPoint(point)
            if self.u.GetAncestor(hit,2) != frame['hwnd']:
                raise ValueError("O altă fereastră acoperă punctul ales.")
            self.u.SetCursorPos(point.x,point.y)
            self.send([('mouse',0,2),('mouse',0,4)])
        elif action == 'text':
            text=payload.get('text')
            if not isinstance(text,str) or not 1 <= len(text) <= 4000 or any(ord(ch)<32 and ch not in '\n\r\t' for ch in text):
                raise ValueError("Introdu între 1 și 4000 de caractere.")
            # Newlines/tabs become spaces; text insertion never presses Enter.
            raw=text.replace('\r',' ').replace('\n',' ').replace('\t',' ').encode('utf-16-le')
            events=[]
            for i in range(0,len(raw),2):
                unit=int.from_bytes(raw[i:i+2],'little')
                events.extend([('unicode',unit,0),('unicode',unit,2)])
            self.send(events)
        elif action == 'key' and payload.get('key') in ('enter','backspace','escape'):
            vk={'enter':13,'backspace':8,'escape':27}[payload['key']]
            self.send([('key',vk,0),('key',vk,2)])
        elif action == 'scroll' and payload.get('direction') in ('up','down'):
            left,top,right,bottom=frame['rect']
            point=w.POINT((left+right)//2,(top+bottom)//2)
            if self.u.GetAncestor(self.u.WindowFromPoint(point),2) != frame['hwnd']:
                raise ValueError("O altă fereastră acoperă ChatGPT.")
            self.u.SetCursorPos(point.x,point.y)
            self.send([('mouse',360 if payload['direction']=='up' else -360,0x800)])
        else:
            raise ValueError("Comandă invalidă.")

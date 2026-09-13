"""Authenticated remote-view routes, registered under the runner's auth hook."""
import base64
import secrets
import threading
import time

from flask import Blueprint, abort, jsonify, render_template, request, session

remote = Blueprint('remote', __name__)
_backend = None
_lock = threading.RLock()
_frames = {}


def backend():
    global _backend
    if _backend is None:
        from desktop_control import WindowsDesktop
        _backend = WindowsDesktop()
    return _backend


def owner():
    if 'remote_owner' not in session:
        session['remote_owner'] = secrets.token_urlsafe(24)
    return session['remote_owner']


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    return data


@remote.route('/remote')
def remote_page():
    owner()
    return render_template('remote.html')


@remote.route('/remote/windows')
def windows():
    with _lock:
        try:
            return jsonify(ok=True, windows=backend().windows())
        except (ValueError, OSError) as error:
            return jsonify(ok=False, error=str(error)), 409


@remote.route('/remote/frame', methods=['POST'])
def frame():
    data = body()
    hwnd = data.get('window')
    if type(hwnd) is not int or hwnd <= 0:
        return jsonify(ok=False, error='Alege fereastra ChatGPT.'), 400
    with _lock:
        now = time.monotonic()
        for key in list(_frames):
            if now - _frames[key]['time'] > 20 or _frames[key]['owner'] == owner():
                del _frames[key]
        if len(_frames) >= 64:
            return jsonify(ok=False, error='Prea multe sesiuni active.'), 429
        try:
            picture, metadata = backend().capture(hwnd)
            token = secrets.token_urlsafe(24)
            _frames[token] = dict(meta=metadata, owner=owner(), time=time.monotonic())
            return jsonify(ok=True, token=token, title=metadata['title'], image='data:image/jpeg;base64,'+base64.b64encode(picture).decode())
        except (ValueError, OSError) as error:
            return jsonify(ok=False, error=str(error)), 409


@remote.route('/remote/activate', methods=['POST'])
def activate():
    data = body()
    hwnd = data.get('window')
    if type(hwnd) is not int or hwnd <= 0:
        return jsonify(ok=False, error='Alege fereastra ChatGPT.'), 400
    with _lock:
        try:
            backend().activate(hwnd)
            return jsonify(ok=True)
        except (ValueError, OSError) as error:
            return jsonify(ok=False, error=str(error)), 409


@remote.route('/remote/action', methods=['POST'])
def action():
    data = body()
    token = data.get('token')
    if not isinstance(token, str):
        return jsonify(ok=False, error='Actualizează imaginea înainte de comandă.'), 409
    with _lock:
        record = _frames.get(token)
        if not record or record['owner'] != owner() or time.monotonic()-record['time'] > 20:
            return jsonify(ok=False, error='Imagine expirată. Actualizează și încearcă din nou.'), 409
        del _frames[token]  # Input is never retried against the same frame.
        try:
            backend().action(record['meta'], data)
            return jsonify(ok=True)
        except (ValueError, OSError) as error:
            return jsonify(ok=False, error=str(error)), 409

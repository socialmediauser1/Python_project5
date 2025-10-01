from TemplateEngine import TemplateEngine
from typing import Callable, List
from handling import handle_hello_person, handle_profile, handle_status, handle_tasks
import time

class AntoniiFramework:
    def __init__(self):
        self.routes = {}
        self.dynamic_routes = {}
        self.middlewares: List[Callable] = []

    def add_middleware(self, middleware: Callable) -> None:
        self.middlewares.append(middleware)

    def middleware(self, type_: str):
        def decorator(fn: Callable):
            self.middlewares.append(fn)
            return fn
        return decorator

    def add_route(self, method, path, handler):
        if '<' in path and '>' in path:
            pattern_parts, param_names, param_types = self.splitter(path)
            self.dynamic_routes.setdefault(method, []).append(
                (pattern_parts, param_names, param_types, handler)
            )
        else:
            self.routes[(method, path)] = handler

    def splitter(self, path: str):
        parts = path.split('/')
        param_names = []
        param_types = []
        for part in parts:
            if part.startswith('<') and part.endswith('>'):
                inside = part[1:-1]
                if ':' in inside:
                    name, type_name = inside.split(':', 1)
                else:
                    name, type_name = inside, 'str'
                param_names.append(name)
                param_types.append(type_name)
        return parts, param_names, param_types

    def get(self, path):
        def decorator(fn):
            self.add_route('GET', path, fn)
            return fn
        return decorator

    def post(self, path):
        def decorator(fn):
            self.add_route('POST', path, fn)
            return fn
        return decorator

    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET').upper()
        path = environ.get('PATH_INFO', '/')
        handler = self.routes.get((method, path))
        params_kwargs = {}
        saw_type_conversion_error = False

        if handler is None:
            path_parts = path.split('/')
            for pattern_parts, param_names, param_types, candidate in self.dynamic_routes.get(method, []):
                if len(pattern_parts) != len(path_parts):
                    continue
                captured = {}
                matched = True
                param_index = 0
                for pattern_part, path_part in zip(pattern_parts, path_parts):
                    if pattern_part.startswith('<') and pattern_part.endswith('>'):
                        name = param_names[param_index]
                        type = param_types[param_index]
                        param_index += 1
                        try:
                            if type == 'int':
                                value = int(path_part)
                            elif type in ('str', '', None):
                                value = path_part
                            else:
                                value = path_part
                            captured[name] = value
                        except Exception:
                            matched = False
                            saw_type_conversion_error = True
                            break
                    else:
                        if pattern_part != path_part:
                            matched = False
                            break
                if matched:
                    handler = candidate
                    params_kwargs = captured
                    break

        if handler is None and saw_type_conversion_error:
            start_response('400 Bad Request', [('Content-Type', 'text/plain; charset=utf-8')])
            return [b'Bad Request']

        if handler is None:
            start_response('404 Not Found', [('Content-Type', 'text/plain; charset=utf-8')])
            return [b'Not Found']

        if method == 'POST':
            try:
                length = int(environ.get('CONTENT_LENGTH', 0) or 0)
            except (ValueError, TypeError):
                length = 0
            body = environ['wsgi.input'].read(length) if length > 0 else b''
            args = (body.decode('utf-8'),)
        else:
            args = ()

        def middleware_handler():
            return handler(*args, **params_kwargs) if params_kwargs else handler(*args)

        for middleware in reversed(self.middlewares):
            next_layer = middleware_handler
            def make_layer(middleware, nxt):
                def layer():
                    return middleware(environ, nxt)
                return layer
            middleware_handler = make_layer(middleware, next_layer)

        result = middleware_handler()

        status = '200 OK'
        extra_headers = []
        body_value = result
        if isinstance(result, tuple):
            if len(result) == 3:
                body_value, status, extra_headers = result
            elif len(result) == 2:
                body_value, status = result

        if isinstance(body_value, bytes):
            body_bytes = body_value
        else:
            body_bytes = str(body_value).encode('utf-8')

        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body_bytes))),
        ]
        if 'extra_response_headers' in environ and isinstance(environ['extra_response_headers'], list):
            headers.extend(environ['extra_response_headers'])
        if extra_headers:
            headers.extend(extra_headers)

        start_response(status, headers)
        return [body_bytes]

app = AntoniiFramework()
template = TemplateEngine()
def _html(str):
    return str


def logging_middleware(environ, next_):
    path = environ.get('PATH_INFO', '/')
    print(f"[log] -> before {path}")
    result = next_()
    print(f"[log] <- after  {path}")
    return result

def timing_middleware(environ, next_):
    start = time.perf_counter()
    result = next_()
    duration_ms = (time.perf_counter() - start) * 1000.0
    headers = environ.setdefault('', [])
    headers.append(('process time', f"{duration_ms:.2f}ms"))
    print(f"[time] {environ.get('PATH_INFO','/')} took {duration_ms:.2f}ms")
    return result

def authorization_middleware(environ, next_):
    path = environ.get('PATH_INFO', '/')
    if path.startswith('/secure'):
        token = environ.get('HTTP_AUTHORIZATION', '')
        if token != 'valid':
            body = 'Unauthorized'
            return body, '401 Unauthorized', [('Content-Type', 'text/plain; charset=utf-8')]
    return next_()

def footer_middleware(environ, next_):
    result = next_()
    comment = "<Antonii Framework>"
    if isinstance(result, tuple):
        body, status, *rest = result + (None,)
        extra_headers = rest[0] if rest and rest[0] is not None else []
        if isinstance(body, bytes):
            try:
                body_str = body.decode('utf-8') + comment
                return body_str, status, extra_headers
            except Exception:
                return result
        else:
            return str(body) + comment, status, extra_headers
    else:
        if isinstance(result, bytes):
            try:
                return result.decode('utf-8') + comment
            except Exception:
                return result
        return str(result) + comment

app.add_middleware(logging_middleware)
app.add_middleware(timing_middleware)

@app.middleware('auth')
def auth(environ, next_):
    return authorization_middleware(environ, next_)

@app.middleware('footer')
def footer(environ, next_):
    return footer_middleware(environ, next_)

@app.get('/hello/<name>/<age:int>/<city>')
def hello_person(name, age, city):
    return handle_hello_person(name, age, city)

@app.get('/profile/<name>/<age:int>')
def profile(name, age):
    return handle_profile(name, age)

@app.get('/status/<temperature:int>')
def status(temperature):
    return handle_status(temperature)

@app.get('/tasks')
def tasks():
    return handle_tasks()

@app.get('/log-test')
def log_test():
    return 'Log test ok'

@app.get('/time-test')
def time_test():
    return 'Time test ok'

@app.get('/secure')
def secure():
    return 'Secure content accessed'

@app.get('/footer-test')
def footer_test():
    return 'Footer should append here'
"""Optional installed OpenBB environment; fixed read-only calls, JSON boundary."""

import json
import subprocess

from rocket.config import env

_SCRIPT = '''
import contextlib, json, sys
request = json.loads(sys.stdin.read())
with contextlib.redirect_stdout(sys.stderr):
    from openbb import obb
    routes = {"cftc.cot": obb.cftc.cot, "news.company": obb.news.company, "news.world": obb.news.world}
    result = routes[request["route"]](**request["params"])
print(json.dumps([r.model_dump(mode="json") for r in result.results]))
'''


def read_openbb(route, **params):
    if route not in {"cftc.cot", "news.company", "news.world"}:
        raise ValueError("unsupported OpenBB capability")
    executable = env("OPENBB_PYTHON")
    if executable:
        process = subprocess.run([executable, "-c", _SCRIPT], input=json.dumps({"route": route, "params": params}),
                                 text=True, capture_output=True, timeout=60, check=False)
        if process.returncode:
            # OpenBB exception text can contain credential-bearing URLs.
            raise RuntimeError("OpenBBReadFailed")
        return json.loads(process.stdout)
    from openbb import obb
    target = {"cftc.cot": obb.cftc.cot, "news.company": obb.news.company, "news.world": obb.news.world}[route]
    return target(**params)

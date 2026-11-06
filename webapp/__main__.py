import argparse

from .app import create_app

ap = argparse.ArgumentParser(description="Run the Ancestor Finder web interface")
ap.add_argument("--records", help="records CSV (default: the invented demo family)")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=8000)
args = ap.parse_args()
create_app(args.records).run(host=args.host, port=args.port, debug=False)

import argparse

import sys
import threading

from .app import create_app, warm_indexes

ap = argparse.ArgumentParser(description="Run the Ancestor Finder web interface")
ap.add_argument("--records", help="records CSV (default: the invented demo family)")
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--port", type=int, default=8000)
args = ap.parse_args()
app = create_app(args.records)
cov = app.config["COVERAGE"]
if not cov["records"]:
    sys.exit(f"Fant ingen oppføringer i {app.config['RECORDS_PATH']}.\n"
             "Filen er tom. Som regel betyr det at nedlastingen eller importen ikke fikk med noe.\n"
             "Kjør tools/fetch_census.py og import_census.py på nytt, og se etter feilmeldinger.\n"
             "Uten --records bruker appen eksempelfamilien.")
print(f"{cov['records']} oppføringer · {', '.join(map(str, cov['years']))} · {', '.join(cov['counties'])}")
threading.Thread(target=warm_indexes, args=(app,), daemon=True).start()
app.run(host=args.host, port=args.port, debug=False)

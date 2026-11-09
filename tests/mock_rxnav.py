"""Tiny stand-in for the RxNav API, used only to test the pipeline offline.
It implements the four endpoints the project uses with a handful of real-looking concepts."""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rapidfuzz import fuzz, process

C = {  # rxcui: (name, tty, [ingredient rxcuis])
    "161": ("acetaminophen", "IN", []), "202433": ("Tylenol", "BN", ["161"]),
    "327361": ("adalimumab", "IN", []), "352056": ("Humira", "BN", ["327361"]),
    "29046": ("lisinopril", "IN", []), "6809": ("metformin", "IN", []),
    "861004": ("metformin hydrochloride", "PIN", ["6809"]), "5640": ("ibuprofen", "IN", []),
    "153008": ("Advil", "BN", ["5640"]), "5489": ("hydrocodone", "IN", []),
    "214182": ("acetaminophen / hydrocodone", "MIN", ["161", "5489"]),
    "36567": ("simvastatin", "IN", []), "196503": ("Zocor", "BN", ["36567"]),
    "1364430": ("apixaban", "IN", []), "1364435": ("Eliquis", "BN", ["1364430"]),
    "1876376": ("dupilumab", "IN", []), "1876379": ("Dupixent", "BN", ["1876376"]),
    "1991302": ("semaglutide", "IN", []), "1991306": ("Ozempic", "BN", ["1991302"]),
    "8640": ("prednisone", "IN", []), "6918": ("methotrexate", "IN", []),
}
BY_NAME = {v[0].lower(): k for k, v in C.items()}
EXTRA_EXACT = {"metformin hcl": "861004", "paracetamol": "161", "hydrocodone bitartrate / acetaminophen": "214182"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        p = u.path.replace("/REST", "")
        if p == "/rxcui.json":
            n = qs.get("name", "").lower().strip()
            rx = BY_NAME.get(n) or EXTRA_EXACT.get(n)
            return self.send({"idGroup": {"rxnormId": [rx]} if rx else {}})
        if p == "/approximateTerm.json":
            term = qs.get("term", "").lower()
            hits = process.extract(term, {k: v[0].lower() for k, v in C.items()}, scorer=fuzz.WRatio, limit=5)
            cands = [{"rxcui": k, "score": str(s), "rank": str(i + 1), "name": C[k][0], "source": "RXNORM"}
                     for i, (_, s, k) in enumerate(hits)]
            return self.send({"approximateGroup": {"candidate": cands}})
        parts = p.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "rxcui" and parts[1] in C:
            rx = parts[1]
            name, tty, ings = C[rx]
            if parts[2] == "properties.json":
                return self.send({"properties": {"rxcui": rx, "name": name, "tty": tty}})
            if parts[2] == "related.json":
                want = qs.get("tty", "").replace("+", " ").split()
                groups = []
                for t in want:
                    props = [{"rxcui": i, "name": C[i][0], "tty": C[i][1]} for i in ings if C[i][1] == t]
                    groups.append({"tty": t, "conceptProperties": props} if props else {"tty": t})
                return self.send({"relatedGroup": {"conceptGroup": groups}})
        return self.send({})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()

from pathlib import Path
import json,sys
R=Path(__file__).resolve().parent;d=json.loads((R/'analysis.json').read_text());payload={k:d[k] for k in ['summary','rows','engines','trials','utf8_audit','volume_domain_audit']}
html=(R/'dashboard.html').read_text(encoding='utf8').replace('__DATA__',json.dumps(payload,ensure_ascii=False).replace('<','\\u003c'))
dest=Path(sys.argv[1]) if len(sys.argv)>1 else R/'TABLEAU-DE-BORD.html';dest.write_text(html,encoding='utf8');print(dest)

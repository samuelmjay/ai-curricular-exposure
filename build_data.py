"""Build dashboard data from the revised (Sept 2026) volume JSON. Public catalog data only; no PII."""
import json, glob, os, sys, collections
sys.path.insert(0, os.path.expanduser('~/claude-drive/work/update_2026-09'))
from rule import BANDS, F4_CAP, F5_CAP
REV = os.path.expanduser('~/claude-drive/work/update_2026-09/rev')
CAT = os.path.expanduser('~/claude-drive/work/catalog/courses.jsonl')
cat = {}
for l in open(CAT):
    c = json.loads(l); cat[c['course_id']] = c
changes = {c['course_id']: c for c in json.load(open(os.path.expanduser('~/claude-drive/work/update_2026-09/changes.json')))}
COL_SHORT = {'College of Letters, Arts and Sciences': 'CLAS', 'College of Health and Human Sciences': 'CHHS',
             'College of Aerospace, Computing, Engineering, and Design': 'CACED', 'College of Business': 'COB',
             'School of Education': 'SOE', 'School of Hospitality': 'SOH'}

def trace(c, h):
    """Why the rating is what it is at horizon h: task band, after dampener, binding cap."""
    f1, f2, f3, f4, f5 = (c[k][h] for k in ('f1', 'f2', 'f3', 'f4', 'f5'))
    task = 2 if f1 >= 4 else 1 if f1 == 3 else 0
    damp = max(0, task - 1) if (f2 <= 2 or f3 <= 2) else task
    b = damp
    cap4 = F4_CAP.get(f4, [None] * 3)[h]; cap5 = F5_CAP.get(f5, [None] * 3)[h]
    for cap in (cap4, cap5):
        if cap: b = min(b, BANDS.index(cap))
    by = '' if b == damp else ('lockin' if cap4 and BANDS.index(cap4) == b else 'found')
    return task, damp, b, by

import re
def scrub(t):
    # published catalog text sometimes lists department contacts; the dashboard doesn't need them
    t = re.sub(r'[\w.+-]+@[\w-]+\.[\w.]*\w', '[contact omitted]', t or '')
    return re.sub(r'\(?\b\d{3}[-.)\s]\s?\d{3}[-.]\d{4}\b', '[contact omitted]', t)

rows, prefix_reason = [], collections.defaultdict(dict)
for p in sorted(glob.glob(f'{REV}/vol_*.json')):
    vol = json.load(open(p))
    if vol['college'].startswith('Honors'):  # MSU Denver has no Honors college; left out of the dashboard
        continue
    col = COL_SHORT[vol['college']]
    for pref, cs in vol['prefixes'].items():
        for c in cs:
            k = c['course_id']; cc = cat.get(k, {})
            tr = [trace(c, h) for h in range(3)]
            assert all(BANDS[t[2]] == c['ratings'][h] for h, t in enumerate(tr)), k
            rows.append({
                'id': k, 'p': pref, 't': c['title'], 'cr': c['credit_hours'], 'col': col,
                'dept': cc.get('owning_department') or '', 'lv': cc.get('level') or '',
                'gs': 1 if cc.get('general_studies_designation') else 0,
                'r': [BANDS.index(x) for x in c['ratings']],
                'f': [c['f1'], c['f2'], c['f3'], c['f4'], c['f5']],
                'task': [t[0] for t in tr],           # band from F1 alone
                'held': [t[3] for t in tr],           # cap holding it below its dampened task band
                'damp': [1 if t[1] < t[0] else 0 for t in tr],
                'cf': {'high': 2, 'medium': 1, 'medium-high': 1, 'low': 0}[c['confidence']],
                'u': 1 if k in changes else 0, 'uc': 1 if k in changes and changes[k]['rating_changed'] else 0,
            })
            prefix_reason[pref][k] = {'r': [scrub(c['reasoning_24m']), scrub(c['reasoning_5y']), scrub(c['reasoning_10y'])],
                                      'n': c.get('update_note'), 'd': scrub(cc.get('description'))}
os.makedirs('data/reasons', exist_ok=True)
for pref, d in prefix_reason.items():
    json.dump(d, open(f'data/reasons/{pref}.json', 'w'), separators=(',', ':'), ensure_ascii=False)
open('data/courses.js', 'w').write('window.COURSES=' + json.dumps(rows, separators=(',', ':'), ensure_ascii=False) + ';')
print(len(rows), 'courses', len(prefix_reason), 'prefixes')
held5 = collections.Counter(r['held'][1] for r in rows)
print('held at 5yr:', held5)
print('F1>=4 at 5yr but not High:', sum(1 for r in rows if r['task'][1] == 2 and r['r'][1] < 2))

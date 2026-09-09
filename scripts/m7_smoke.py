"""M7 smoke: geo DAO + map router + annotate(zones=) — quick verification."""
import pathlib
import tempfile

from backend.db.connection import Database
from backend.db.migrations import MIGRATIONS
from backend.db.dao import DAO

tmp = pathlib.Path(tempfile.mkdtemp())
db = Database(tmp / 't.db')
db.migrate(MIGRATIONS)
dao = DAO(db)
dao.upsert_source('file:x.mp4', 'file')
print('set_source_geo:', dao.set_source_geo('file:x.mp4', 12.9716, 77.5946, 'North Gate'))
r = dao.get_source('file:x.mp4')
print('lat/lng/label:', r['latitude'], r['longitude'], r['label'])
print('insert sector:', dao.insert_geo_sector('gs-1', 'Alpha', 'sector', 'demo',
                                              '[[12.97,77.59],[12.98,77.60],[12.96,77.61]]'))
rows = dao.sources_rows()
print('sources_rows:', rows[0]['latitude'], rows[0]['label'])
print('geo_sectors_rows:', [s['name'] for s in dao.geo_sectors_rows()])

from backend.api.map import load_maps_key  # noqa: E402
print('key loaded (non-empty):', bool(load_maps_key()))

import numpy as np  # noqa: E402
from backend.vision.annotation import annotate  # noqa: E402
f = np.zeros((480, 640, 3), np.uint8)
out = annotate(f, [], pipeline_fps=10.0, device='cpu',
               zones=[{'kind': 'polygon', 'zone_type': 'RESTRICTED',
                       'name': 'GATE',
                       'geometry': {'points': [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]}}])
print('annotate w/ zones ok:', out.shape == f.shape)
# malformed zone must not raise
out2 = annotate(f, [], zones=[{'kind': 'polygon', 'geometry': {'points': 'garbage'}}])
print('annotate malformed-zone ok:', out2.shape == f.shape)
print('M7 smoke: ALL OK')

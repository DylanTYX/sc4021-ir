import json
import os
import sys
import requests

from datetime import datetime, timezone, timedelta

SOLR_UPDATE_URL = "http://localhost:8983/solr/political_opinions/update?commit=true"

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "singapore_wp_comments_display_inference_id.json")

# Convert date string into Solr's expected ISO 8601 format
def convert_date(date_str):
    # Parse the date string with timezone offset
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
    # Convert to UTC
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

# Load documents
with open(json_path, "r", encoding="utf-8") as f:
    docs = json.load(f)

# Change date string format
DATE = "created_at"
for doc in docs:
    if DATE in doc and doc[DATE]:
        doc[DATE] = convert_date(doc[DATE])

# Post to Solr via JSON update handler
response = requests.post(
    SOLR_UPDATE_URL,
    headers={"Content-Type": "application/json"},
    data=json.dumps(docs),
    timeout=30,
)

if response.ok:
    print(f"✅ Indexed {len(docs)} documents into Solr core 'political_opinions'")
else:
    print(
        f"❌ Indexing failed — HTTP {response.status_code}: {response.text}",
        file=sys.stderr,
    )
    sys.exit(1)

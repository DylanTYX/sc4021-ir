import json
import os
import sys
import requests

SOLR_UPDATE_URL = "http://localhost:8983/solr/political_opinions/update?commit=true"

current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "mock_data.json")

# Load documents
with open(json_path, "r", encoding="utf-8") as f:
    docs = json.load(f)

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

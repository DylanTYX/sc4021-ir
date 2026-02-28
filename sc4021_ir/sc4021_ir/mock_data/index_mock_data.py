import pysolr
import json
import os

# Solr URL for your core
SOLR_URL = "http://localhost:8983/solr/mrt_opinions"
solr = pysolr.Solr(SOLR_URL, always_commit=True)

# Path to mock data JSON
current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "mock_data.json")

# Load mock data
with open(json_path, "r") as f:
    docs = json.load(f)

# Index data into Solr
solr.add(docs)

print(f"✅ Indexed {len(docs)} mock documents into Solr core 'mrt_opinions'")

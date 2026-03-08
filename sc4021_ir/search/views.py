from django.shortcuts import render
import pysolr
import json
from collections import defaultdict
from dateutil import parser
from collections import Counter

# Solr connection
SOLR_URL = "http://localhost:8983/solr/political_opinions"
solr = pysolr.Solr(SOLR_URL, always_commit=True)

ROWS_PER_PAGE = 10

# Maps sort_by request parameter → Solr sort expression
SORT_OPTIONS = {
    "relevance": "score desc",
    "newest": "created_at desc",
    "oldest": "created_at asc",
    "upvotes": "upvotes desc",
}


# Main search view
def search_view(request):
    query = request.GET.get("q", "").strip()
    selected_sentiment = request.GET.get("sentiment", "").strip()
    selected_party = request.GET.get("party", "").strip()
    selected_person = request.GET.get("person", "").strip()
    date_start = request.GET.get("date_start", "").strip()  # YYYY-MM-DD
    date_end = request.GET.get("date_end", "").strip()  # YYYY-MM-DD
    sort_by = request.GET.get("sort_by", "relevance").strip()
    page_num = max(1, int(request.GET.get("page", 1)))
    election_year = request.GET.get("election_year", "").strip()

    # Full-text search on the "text" field; fall back to match-all
    solr_query = f"text:({query})" if query else "*:*"

    # Filter queries (fq)
    fq = _build_filter_queries(
        selected_sentiment, selected_party, selected_person, date_start, date_end, election_year
    )

    # Sort
    sort = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["relevance"])

    # Pagination
    start = (page_num - 1) * ROWS_PER_PAGE

    # Execute search
    try:
        search_kwargs = {
            "fl": "id,text,sentiment,sentiment_score,party,person,created_at,upvotes",
            "sort": sort,
        }
        if fq:
            search_kwargs["fq"] = fq

        results = solr.search(
            solr_query, start=start, rows=ROWS_PER_PAGE, **search_kwargs
        )
    except Exception as e:
        return render(
            request, "search/index.html", {"error": f"Solr query failed: {e}"}
        )

    # Map results to template-friendly dicts
    mapped_results = []
    for doc in results:
        raw_date = doc.get("created_at")
        mapped_results.append(
            {
                "id": doc.get("id", ""),
                "text": doc.get("text", ""),
                "sentiment": doc.get("sentiment", ""),
                "sentiment_score": doc.get("sentiment_score"),
                "party": doc.get("party", []),
                "person": doc.get("person", []),
                "created_at": parser.parse(raw_date) if raw_date else None,
                "upvotes": doc.get("upvotes", 0),
            }
        )

    total_results = results.hits
    total_pages = max(1, (total_results + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)

    # Chart data
    chart_data = get_sentiment_distribution(solr_query, fq)

    # Word cloud data
    wordcloud_data = get_wordcloud_data(solr_query, fq)

    # Template context
    context = {
        "query": query,
        "selected_sentiment": selected_sentiment,
        "selected_party": selected_party,
        "selected_person": selected_person,
        "date_start": date_start,
        "date_end": date_end,
        "sort_by": sort_by,
        "page": page_num,
        "total_pages": total_pages,
        "total_results": total_results,
        "results": mapped_results,
        "chart_data": json.dumps(chart_data),
        "wordcloud_data": json.dumps(wordcloud_data),
        "election_year": election_year,
    }

    return render(request, "search/index.html", context)


# Helper: build filter queries list
def _build_filter_queries(sentiment, party, person, date_start, date_end, election_year):
    """Return a list of Solr fq strings based on active filter values."""
    fq = []

    if sentiment:
        fq.append(f"sentiment:{sentiment}")

    if party:
        # Quote multi-word values
        fq.append(f'party:"{party}"')

    if person:
        fq.append(f'person:"{person}"')

    if date_start or date_end:
        start = f"{date_start}T00:00:00Z" if date_start else "*"
        end = f"{date_end}T23:59:59Z" if date_end else "*"
        fq.append(f"created_at:[{start} TO {end}]")

    if election_year == "2020":
        fq.append("created_at:[2020-06-01T00:00:00Z TO 2020-07-31T23:59:59Z]")

    elif election_year == "2025":
        fq.append("created_at:[2025-04-01T00:00:00Z TO 2025-05-31T23:59:59Z]")

    return fq


# Helper: sentiment distribution per party for Chart.js
def get_sentiment_distribution(solr_query, fq):
    """Return sentiment counts broken down by party for Chart.js stacked/pie charts."""
    try:
        search_kwargs = {
            "rows": 0,
            "facet": "on",
            "facet.pivot": "party,sentiment",
            "facet.mincount": 1,
        }
        if fq:
            search_kwargs["fq"] = fq

        facet_results = solr.search(solr_query, **search_kwargs)

        parties_data = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})

        pivot = facet_results.raw_response.get("facet_counts", {}).get(
            "facet_pivot", {}
        )

        for party_item in pivot.get("party,sentiment", []):
            party_name = party_item["value"]
            for sentiment_item in party_item.get("pivot", []):
                parties_data[party_name][sentiment_item["value"]] = sentiment_item[
                    "count"
                ]

        sorted_parties = sorted(parties_data.keys())
        return {
            "labels": sorted_parties,
            "positive": [parties_data[p]["positive"] for p in sorted_parties],
            "neutral": [parties_data[p]["neutral"] for p in sorted_parties],
            "negative": [parties_data[p]["negative"] for p in sorted_parties],
        }

    except Exception:
        return {"labels": [], "positive": [], "neutral": [], "negative": []}

# Helper: pre-processing of data for word cloud generation
def get_wordcloud_data(solr_query, fq, top_n=50):
    #get up to 1000 docs
    results = solr.search(solr_query, rows=1000, fl="text", fq=fq)

    #concatenate all text
    all_text = " ".join([doc.get("text", "") for doc in results])

    #basic word filtering
    stopwords = {"the", "its", "still", "with", "but", "and", "is", "to", "of", "in", "a", "for", "on"}  # you can expand
    words = [w for w in all_text.split() if w.lower() not in stopwords]

    #bount word frequencies
    counter = Counter(words)
    return [[word, count] for word, count in counter.most_common(top_n)]
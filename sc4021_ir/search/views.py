from django.shortcuts import render
import pysolr
import json
from collections import defaultdict
from dateutil import parser

# Connect to Solr core
SOLR_URL = "http://localhost:8983/solr/mrt_opinions"
solr = pysolr.Solr(SOLR_URL, always_commit=True)


# Main search view
def search_view(request):
    # Get query parameters
    query = request.GET.get("q", "").strip()
    selected_line = request.GET.get("mrt_line", "")
    selected_aspect = request.GET.get("aspect", "")
    selected_sentiment = request.GET.get("sentiment", "")
    page_num = int(request.GET.get("page", 1))

    rows_per_page = 10

    # Build Solr query string
    query_parts = []
    if query:
        query_parts.append(f"text:({query})")
    if selected_line:
        query_parts.append(f"mrt_line:{selected_line}")
    if selected_aspect:
        query_parts.append(f"aspect:{selected_aspect}")
    if selected_sentiment:
        query_parts.append(f"sentiment:{selected_sentiment}")

    solr_query = " AND ".join(query_parts) if query_parts else "*:*"

    # Pagination
    start = (page_num - 1) * rows_per_page

    # Execute Solr search
    try:
        results = solr.search(
            solr_query,
            start=start,
            rows=rows_per_page,
            **{
                "fl": "text,mrt_line,aspect,sentiment,timestamp,source",
                "sort": "timestamp desc",
            },
        )
    except Exception as e:
        context = {"error": f"Solr query failed: {str(e)}"}
        return render(request, "search/index.html", context)

    # Map Solr results to template
    mapped_results = [
        {
            "text": doc.get("text", ""),
            "mrt_line": doc.get("mrt_line", ""),
            "aspect": doc.get("aspect", ""),
            "sentiment": doc.get("sentiment", ""),
            "timestamp": (
                parser.parse(doc.get("timestamp", "")) if doc.get("timestamp") else None
            ),
            "source": doc.get("source", ""),
        }
        for doc in results
    ]

    total_results = results.hits
    total_pages = (total_results + rows_per_page - 1) // rows_per_page

    # Generate chart data using Solr faceting
    chart_data = get_sentiment_distribution(
        query, selected_line, selected_aspect, selected_sentiment
    )

    # Context to pass to template
    context = {
        "query": query,
        "selected_line": selected_line,
        "selected_aspect": selected_aspect,
        "selected_sentiment": selected_sentiment,
        "page": page_num,
        "total_pages": total_pages,
        "total_results": total_results,
        "results": mapped_results,
        "chart_data": json.dumps(chart_data),
    }

    return render(request, "search/index.html", context)


# Helper: get sentiment distribution for chart
def get_sentiment_distribution(query, mrt_line, aspect, sentiment):
    """
    Returns sentiment counts per aspect for Chart.js
    """
    try:
        # Remove aspect filter for chart to show all aspects
        solr_query = build_solr_query(query, mrt_line, None, sentiment)

        facet_results = solr.search(
            solr_query,
            rows=0,  # only need facets
            **{"facet": "on", "facet.pivot": "aspect,sentiment"},
        )

        aspects_data = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})

        pivot = facet_results.raw_response.get("facet_counts", {}).get(
            "facet_pivot", {}
        )
        aspect_sentiment = pivot.get("aspect,sentiment", [])

        for aspect_item in aspect_sentiment:
            aspect_name = aspect_item["value"]
            for sentiment_item in aspect_item.get("pivot", []):
                sentiment_name = sentiment_item["value"]
                count = sentiment_item["count"]
                aspects_data[aspect_name][sentiment_name] = count

        sorted_aspects = sorted(aspects_data.keys())
        chart_data = {
            "labels": [a.title() for a in sorted_aspects],
            "positive": [aspects_data[a]["positive"] for a in sorted_aspects],
            "neutral": [aspects_data[a]["neutral"] for a in sorted_aspects],
            "negative": [aspects_data[a]["negative"] for a in sorted_aspects],
        }
        return chart_data

    except Exception as e:
        # fallback
        return {"labels": [], "positive": [], "neutral": [], "negative": []}


# Helper: Build Solr query string
def build_solr_query(query, mrt_line, aspect, sentiment):
    query_parts = []
    if query:
        query_parts.append(f"text:({query})")
    if mrt_line:
        query_parts.append(f"mrt_line:{mrt_line}")
    if aspect:
        query_parts.append(f"aspect:{aspect}")
    if sentiment:
        query_parts.append(f"sentiment:{sentiment}")
    return " AND ".join(query_parts) if query_parts else "*:*"

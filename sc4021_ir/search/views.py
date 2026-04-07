from django.shortcuts import render
import pysolr
import json
import re
from collections import defaultdict
from calendar import month_abbr
from dateutil import parser
from collections import Counter

# Solr connection
SOLR_URL = "http://localhost:8983/solr/political_opinions"
solr = pysolr.Solr(SOLR_URL, always_commit=True)

ROWS_PER_PAGE = 10

WORDCLOUD_STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "also",
    "still",
    "really",
    "much",
    "many",
    "one",
    "two",
    "three",
    "would",
    "may",
    "might",
    "must",
    "shall",
    "yet",
    "ever",
    "never",
    "yes",
    "nope",
    "okay",
    "ok",
    "im",
    "ive",
    "id",
    "ill",
    "dont",
    "didnt",
    "doesnt",
    "cant",
    "couldnt",
    "wont",
    "wouldnt",
    "isnt",
    "arent",
    "wasnt",
    "werent",
    "hasnt",
    "havent",
    "hadnt",
    "shouldnt",
    "youre",
    "theyre",
    "were",
    "weve",
    "theyve",
    "thats",
    "theres",
    "whats",
    "lets",
    "amp",
    "http",
    "https",
    "www",
    "com",
    "co",
    "org",
    "net",
    "reddit",
    "rt",
    "via",
}

WORD_PATTERN = re.compile(r"[a-z][a-z']+")

# Maps sort_by request parameter → Solr sort expression
SORT_OPTIONS = {
    "relevance": "score desc",
    "newest": "created_at desc",
    "oldest": "created_at asc",
}

# Canonical party naming for display and filtering.
PARTY_ALIAS_MAP = {
    "Workers' Party": [
        "Workers' Party",
        "Workers Party",
        "workers' party",
        "workers party",
    ],
    "People's Action Party": [
        "People's Action Party",
        "Peoples Action Party",
        "people's action party",
        "peoples action party",
    ],
    "Progress Singapore Party": [
        "Progress Singapore Party",
        "progress singapore party",
    ],
    "Singapore Democratic Party": [
        "Singapore Democratic Party",
        "singapore democratic party",
    ],
    "People's Power Party": [
        "People's Power Party",
        "Peoples Power Party",
        "people's power party",
        "peoples power party",
    ],
}

PARTY_CANONICAL_LOOKUP = {
    alias.strip().lower(): canonical
    for canonical, aliases in PARTY_ALIAS_MAP.items()
    for alias in aliases
}


def canonical_party_name(value):
    if not value:
        return value
    return PARTY_CANONICAL_LOOKUP.get(value.strip().lower(), value)


def get_party_filter_values(selected_party):
    """Return all raw index values that should match a selected canonical party."""
    if not selected_party:
        return []

    target = canonical_party_name(selected_party)
    matches = set(PARTY_ALIAS_MAP.get(target, []))

    # Include canonical and user-provided forms as a safe fallback.
    matches.add(target)
    matches.add(selected_party)
    return sorted(matches)


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
    selected_party = canonical_party_name(selected_party)

    # Full-text search on the "text" field; fall back to match-all
    solr_query = f"text:({query})" if query else "*:*"

    # Filter queries (fq)
    fq = _build_filter_queries(
        selected_sentiment,
        selected_party,
        selected_person,
        date_start,
        date_end,
        election_year,
    )

    # Sort
    sort = SORT_OPTIONS.get(sort_by, SORT_OPTIONS["relevance"])

    # Pagination
    start = (page_num - 1) * ROWS_PER_PAGE

    # Get dynamic dropdown options from indexed values
    party_options, person_options = get_filter_options()

    # Execute search
    try:
        search_kwargs = {
            "fl": "text,clean_text,sentiment,sentiment_score,party,person,aspect,created_at,id",
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
                "text": doc.get("text", ""),
                "clean_text": doc.get("clean_text", ""),
                "sentiment": doc.get("sentiment", ""),
                "sentiment_score": doc.get("sentiment_score"),
                "party": [
                    canonical_party_name(party) for party in doc.get("party", [])
                ],
                "person": doc.get("person", []),
                "aspect": doc.get("aspect", []),
                "created_at": parser.parse(raw_date) if raw_date else None,
                "id": doc.get("id", ""),
            }
        )

    total_results = results.hits
    total_pages = max(1, (total_results + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)

    # Chart data
    chart_data = get_sentiment_distribution(solr_query, fq)
    trend_data = get_sentiment_trend(solr_query, fq)
    chart_data.update(trend_data)

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
        "trend_insight": chart_data.get("trend_insight", ""),
        "trend_insights": chart_data.get("trend_insights", []),
        "party_options": party_options,
        "person_options": person_options,
    }

    return render(request, "search/index.html", context)


# Helper: build filter queries list
def _build_filter_queries(
    sentiment, party, person, date_start, date_end, election_year
):
    """Return a list of Solr fq strings based on active filter values."""
    fq = []

    if sentiment:
        fq.append(f"sentiment:{sentiment.capitalize()}")

    if party:
        party_values = get_party_filter_values(party)
        if len(party_values) == 1:
            fq.append(f'party:"{party_values[0]}"')
        else:
            party_or = " OR ".join([f'party:"{value}"' for value in party_values])
            fq.append(f"({party_or})")

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


def get_filter_options():
    """Return party/person options directly from Solr index values, sorted alphabetically."""
    try:
        facet_results = solr.search(
            "*:*",
            rows=0,
            **{
                "facet": "on",
                "facet.field": ["party", "person"],
                "facet.mincount": 1,
                "facet.limit": -1,
            },
        )

        facet_fields = facet_results.raw_response.get("facet_counts", {}).get(
            "facet_fields", {}
        )

        party_values = _parse_facet_values(facet_fields.get("party", []))
        person_values = _parse_facet_values(facet_fields.get("person", []))

        canonical_party_values = sorted(
            {canonical_party_name(value) for value in party_values},
            key=lambda s: s.lower(),
        )

        party_options = [
            {"value": value, "label": value} for value in canonical_party_values
        ]
        person_options = [
            {"value": value, "label": value}
            for value in sorted(person_values, key=lambda s: s.lower())
        ]

        return party_options, person_options
    except Exception:
        return [], []


def _parse_facet_values(facet_list):
    """Convert Solr facet field list format [value, count, ...] to value list."""
    values = []
    for i in range(0, len(facet_list), 2):
        value = facet_list[i]
        if value:
            values.append(value)
    return values


# Helper: sentiment distribution per party for Chart.js
def get_sentiment_distribution(solr_query, fq):
    """Return sentiment counts broken down by party for Chart.js stacked/pie charts."""
    try:
        search_kwargs = {
            "rows": 0,
            "facet": "on",
            "facet.field": "sentiment",  # pie chart
            "facet.pivot": "party,sentiment",  # bar graph
            "facet.mincount": 1,
        }
        if fq:
            search_kwargs["fq"] = fq

        facet_results = solr.search(solr_query, **search_kwargs)
        facet_counts = facet_results.raw_response.get("facet_counts", {})

        # For pie chart (sentiment only)
        sentiment_field = facet_counts.get("facet_fields", {}).get("sentiment", [])
        total_sent = {"positive": 0, "neutral": 0, "negative": 0}
        it = iter(sentiment_field)
        for val, count in zip(it, it):
            total_sent[val.lower()] = count

        # For bar graph (party and sentiment)
        parties_data = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
        pivot = facet_counts.get("facet_pivot", {})

        for party_item in pivot.get("party,sentiment", []):
            party_name = canonical_party_name(party_item["value"])
            for sentiment_item in party_item.get("pivot", []):
                parties_data[party_name][sentiment_item["value"].lower()] = (
                    sentiment_item["count"]
                )

        sorted_parties = sorted(parties_data.keys())
        return {
            # For pie chart
            "total_positive": total_sent["positive"],
            "total_neutral": total_sent["neutral"],
            "total_negative": total_sent["negative"],
            # For bar graph
            "labels": sorted_parties,
            "positive": [parties_data[p]["positive"] for p in sorted_parties],
            "neutral": [parties_data[p]["neutral"] for p in sorted_parties],
            "negative": [parties_data[p]["negative"] for p in sorted_parties],
        }

    except Exception:
        return {"labels": [], "positive": [], "neutral": [], "negative": []}


# Helper: sentiment trend over time for Chart.js
def get_sentiment_trend(solr_query, fq):
    """Return monthly sentiment counts and a short insight string."""
    try:
        monthly_counts = defaultdict(
            lambda: {"positive": 0, "neutral": 0, "negative": 0}
        )

        for doc in _fetch_all_solr_docs(solr_query, fq, fl="created_at,sentiment"):
            raw_date = doc.get("created_at")
            sentiment = (doc.get("sentiment") or "").lower()
            if not raw_date or sentiment not in {"positive", "neutral", "negative"}:
                continue

            parsed_date = parser.parse(raw_date)
            bucket_key = (parsed_date.year, parsed_date.month)
            monthly_counts[bucket_key][sentiment] += 1

        if not monthly_counts:
            return {
                "trend_labels": [],
                "trend_positive": [],
                "trend_neutral": [],
                "trend_negative": [],
                "trend_insight": "No dated documents are available yet, so the trend chart has nothing to plot.",
                "trend_insights": [],
            }

        sorted_buckets = sorted(monthly_counts.keys())
        labels = [f"{month_abbr[month]} {year}" for year, month in sorted_buckets]
        trend_positive = [
            monthly_counts[bucket]["positive"] for bucket in sorted_buckets
        ]
        trend_neutral = [monthly_counts[bucket]["neutral"] for bucket in sorted_buckets]
        trend_negative = [
            monthly_counts[bucket]["negative"] for bucket in sorted_buckets
        ]

        totals_by_bucket = [
            trend_positive[i] + trend_neutral[i] + trend_negative[i]
            for i in range(len(labels))
        ]
        dominant_idx = max(
            range(len(totals_by_bucket)), key=totals_by_bucket.__getitem__
        )

        dominant_label = labels[dominant_idx]
        dominant_total = totals_by_bucket[dominant_idx]

        positive_total = sum(trend_positive)
        neutral_total = sum(trend_neutral)
        negative_total = sum(trend_negative)
        overall_sentiments = {
            "positive": positive_total,
            "neutral": neutral_total,
            "negative": negative_total,
        }
        overall_dominant = max(overall_sentiments, key=overall_sentiments.get)

        total_posts = positive_total + neutral_total + negative_total

        def _share(part, whole):
            return (part / whole * 100) if whole else 0

        dominant_month_sentiments = {
            "positive": trend_positive[dominant_idx],
            "neutral": trend_neutral[dominant_idx],
            "negative": trend_negative[dominant_idx],
        }
        dominant_month_sentiment = max(
            dominant_month_sentiments, key=dominant_month_sentiments.get
        )
        dominant_month_sentiment_count = dominant_month_sentiments[
            dominant_month_sentiment
        ]

        latest_idx = len(labels) - 1
        latest_label = labels[latest_idx]
        latest_total = totals_by_bucket[latest_idx]
        latest_month_sentiments = {
            "positive": trend_positive[latest_idx],
            "neutral": trend_neutral[latest_idx],
            "negative": trend_negative[latest_idx],
        }
        latest_month_sentiment = max(
            latest_month_sentiments, key=latest_month_sentiments.get
        )
        latest_month_sentiment_count = latest_month_sentiments[latest_month_sentiment]

        insights = [
            f"Overall sentiment is mostly {overall_dominant} ({overall_sentiments[overall_dominant]} of {total_posts}, {_share(overall_sentiments[overall_dominant], total_posts):.1f}%).",
            f"{dominant_label} had the highest activity ({dominant_total} posts), with sentiment mostly {dominant_month_sentiment} ({dominant_month_sentiment_count} of {dominant_total}, {_share(dominant_month_sentiment_count, dominant_total):.1f}%).",
        ]

        if len(labels) > 1:
            insights.append(
                f"In the latest month ({latest_label}), sentiment is mostly {latest_month_sentiment} ({latest_month_sentiment_count} of {latest_total}, {_share(latest_month_sentiment_count, latest_total):.1f}%)."
            )

        insight = insights[0]

        return {
            "trend_labels": labels,
            "trend_positive": trend_positive,
            "trend_neutral": trend_neutral,
            "trend_negative": trend_negative,
            "trend_insight": insight,
            "trend_insights": insights,
        }

    except Exception:
        return {
            "trend_labels": [],
            "trend_positive": [],
            "trend_neutral": [],
            "trend_negative": [],
            "trend_insight": "Trend data could not be generated for the current filters.",
            "trend_insights": [],
        }


# Helper: pre-processing of data for word cloud generation
def get_wordcloud_data(solr_query, fq, top_n=50):
    # Pull all matching docs to build the word cloud corpus.
    all_text = " ".join(
        doc.get("text", "") for doc in _fetch_all_solr_docs(solr_query, fq, fl="text")
    ).lower()

    # Tokenize with regex to avoid punctuation/URL fragments, then remove stopwords.
    words = []
    for token in WORD_PATTERN.findall(all_text):
        normalized = token.strip("'")
        if len(normalized) <= 1:
            continue
        if normalized in WORDCLOUD_STOPWORDS:
            continue
        words.append(normalized)

    counter = Counter(words)
    return [[word, count] for word, count in counter.most_common(top_n)]


# Helper: generator to fetch all matching Solr documents in batches to avoid memory issues
def _fetch_all_solr_docs(solr_query, fq, fl, batch_size=1000):
    """Yield all Solr documents for a query in fixed-size batches."""
    start = 0

    while True:
        search_kwargs = {"rows": batch_size, "start": start, "fl": fl}
        if fq:
            search_kwargs["fq"] = fq

        results = solr.search(solr_query, **search_kwargs)
        if not results:
            break

        for doc in results:
            yield doc

        start += batch_size
        if len(results) < batch_size:
            break

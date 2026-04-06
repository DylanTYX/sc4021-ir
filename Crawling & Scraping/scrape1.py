import json
import re
import time
from datetime import datetime, timezone

import requests

BASE = "https://api.pullpush.io/reddit/search/comment/"

subreddit = "singapore"
seed_queries = ["wp","worker party" ,  "pritam", "jamus", "sylvia lim", "Faisal manap", "Thia Khiang",
                "Gerald Giam", "Raeesah"]
blocked_phrases = ["sentiment value", "SG_wormsbot", "article", "redditporean/sneakpeek", "github", 'automoderator', 'wormsbot', 'sneakpeakbot',
    'remindmebot', 'totesmessenger']
want = 14000
request_delay_seconds = 0.8
cutoff_utc_ts = int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp())
monthly_cap = 200

params = {
    "subreddit": subreddit,
    "sort": "desc",
    "sort_type": "created_utc",
    "size": 100,
}

all_comments = []
seen_ids = set()
monthly_counts = {}


def matches_seed_term(text, seed):
    t = text or ""
    if seed.lower() == "wp":
        return re.search(r"\bwp\b", t, flags=re.IGNORECASE) is not None
    escaped = re.escape(seed).replace(r"\ ", r"\s+")
    return re.search(rf"\b{escaped}\b", t, flags=re.IGNORECASE) is not None


def contains_blocked_phrase(text):
    t = (text or "").lower()
    return any(phrase in t for phrase in blocked_phrases)


def to_timestamp(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def month_key_utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m")


def month_start_utc_ts(month_key):
    year, month = map(int, month_key.split("-"))
    return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())


print(f"Starting PullPush scrape for r/{subreddit}")
print(f"Target: {want} comments matching any target term\n")

for seed in seed_queries:
    if len(all_comments) >= want:
        break

    before = None
    page = 0
    print(f"Using seed query: {seed}")

    while len(all_comments) < want:
        page += 1
        params["q"] = seed

        if before:
            params["before"] = before
        else:
            params.pop("before", None)

        print(f"[{seed} | Page {page}] Requesting... before={before}")

        try:
            r = requests.get(BASE, params=params, timeout=60)
            r.raise_for_status()
            data = r.json().get("data", [])

            if not data:
                print(f"No more results for seed '{seed}'.\n")
                break

            oldest_ts = to_timestamp(data[-1].get("created_utc"))
            if oldest_ts is None:
                print(f"Invalid created_utc in results for seed '{seed}'. Stopping this seed.\n")
                break

            before = oldest_ts
            matched_this_page = 0
            skipped_cutoff = 0
            skipped_seen = 0
            skipped_no_seed_match = 0
            skipped_blocked = 0
            skipped_month_cap = 0
            page_month_keys = set()

            for comment in data:
                created_ts = to_timestamp(comment.get("created_utc"))
                if created_ts is None or created_ts < cutoff_utc_ts:
                    skipped_cutoff += 1
                    continue

                page_month = month_key_utc(created_ts)
                page_month_keys.add(page_month)

                cid = comment.get("id")
                if cid in seen_ids:
                    skipped_seen += 1
                    continue

                body = comment.get("body", "")

                if not matches_seed_term(body, seed):
                    skipped_no_seed_match += 1
                    continue

                if contains_blocked_phrase(body):
                    skipped_blocked += 1
                    continue

                if monthly_counts.get(page_month, 0) >= monthly_cap:
                    skipped_month_cap += 1
                    continue

                seen_ids.add(cid)
                all_comments.append(comment)
                monthly_counts[page_month] = monthly_counts.get(page_month, 0) + 1
                matched_this_page += 1
                if len(all_comments) >= want:
                    break

            readable_time = datetime.fromtimestamp(before, timezone.utc)
            print(f"  Retrieved {len(data)} comments")
            print(f"  Matched this page: {matched_this_page}")
            print(
                "  Skipped - seen:{}, month_cap:{}, no_seed_match:{}, blocked:{}, cutoff:{}".format(
                    skipped_seen, skipped_month_cap, skipped_no_seed_match, skipped_blocked, skipped_cutoff
                )
            )
            print(f"  Total matched so far: {len(all_comments)}")

            # If every month represented on this page is already capped, jump to before
            # the earliest month start so we do not crawl pages that will all be skipped.
            if matched_this_page == 0 and page_month_keys:
                uncapped_month_exists = any(
                    monthly_counts.get(m, 0) < monthly_cap for m in page_month_keys
                )
                if not uncapped_month_exists:
                    earliest_month = min(page_month_keys)
                    jump_before = float(month_start_utc_ts(earliest_month) - 1)
                    if jump_before < before:
                        before = jump_before
                        readable_time = datetime.fromtimestamp(before, timezone.utc)
                        print(
                            f"  Jumped before capped months to: {before} "
                            f"({readable_time} UTC)"
                        )

            print(f"  Next before timestamp: {before} ({readable_time} UTC)\n")

            if oldest_ts < cutoff_utc_ts:
                print(f"Reached cutoff year for seed '{seed}'. Moving to next seed.\n")
                break

            time.sleep(request_delay_seconds)

        except Exception as e:
            print(f"ERROR on seed '{seed}': {e}")
            break

print("\nDone.")
print(f"Final matched count: {len(all_comments)}")

output_file = "singapore_wp_comments.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_comments, f, ensure_ascii=False, indent=2)

print(f"Saved comments to: {output_file}")

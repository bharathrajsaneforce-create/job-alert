"""
Daily Android Developer Job Alert
----------------------------------
Queries the JSearch API (RapidAPI) for jobs posted "yesterday" across India
and Remote, matching Android/App/Mobile developer keywords, filtered for
entry-level / ~1 year experience, then emails a formatted digest.

Runs for free daily via GitHub Actions (see .github/workflows/daily-job-alert.yml).

Setup:
1. Get a RapidAPI key and subscribe to JSearch (free tier):
   https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
2. Create a Gmail "App Password" (Google Account > Security > 2-Step Verification
   > App Passwords) - do NOT use your normal Gmail password.
3. Set these as GitHub repo secrets (Settings > Secrets and variables > Actions):
     RAPIDAPI_KEY
     EMAIL_ADDRESS      (the Gmail address sending the email)
     EMAIL_APP_PASSWORD (the app password from step 2)
     TO_EMAIL           (where you want to receive the digest)
"""

import os
import time
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------- CONFIG: EDIT THIS SECTION ----------------------

# Keywords to search for. Add/remove as you like.
SEARCH_QUERIES = [
    "Android Developer in India",
    "App Developer in India",
    "Mobile Application Developer in India",
    "Kotlin Developer in India",
    "Android Developer Remote India",
]

# JSearch experience filter. Set to None to disable (recommended) - the API's
# experience tagging is unreliable and combining it with a same-day date filter
# can silently return zero results even when matching jobs exist.
# Options if you want to re-enable it: "no_experience", "under_3_years_experience",
# "more_than_3_years_experience", "no_degree"
EXPERIENCE_FILTER = None

# JSearch date bucket to query: "today", "3days", "week", "month".
# Use "3days" for a safety margin - the script still filters precisely by
# timestamp afterward via is_recent().
DATE_POSTED_BUCKET = "3days"

# How many result pages to pull per query (each page ~10 jobs). Keep low to save API quota.
PAGES_PER_QUERY = 1

# -------------------------------------------------------------------------

RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]
TO_EMAIL = os.environ["TO_EMAIL"]

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


def fetch_jobs_for_query(query: str):
    """Call JSearch API for a single query, posted within the last day."""
    all_jobs = []
    for page in range(1, PAGES_PER_QUERY + 1):
        params = {
            "query": query,
            "page": str(page),
            "num_pages": "1",
            "date_posted": DATE_POSTED_BUCKET,
        }
        if EXPERIENCE_FILTER:
            params["job_requirements"] = EXPERIENCE_FILTER

        try:
            resp = requests.get(JSEARCH_URL, headers=HEADERS, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"Error fetching '{query}' page {page}: {resp.status_code} - {resp.text[:300]}")
            else:
                data = resp.json()
                jobs = data.get("data", [])
                print(f"  '{query}' page {page}: {len(jobs)} raw jobs returned by API")
                all_jobs.extend(jobs)
        except requests.RequestException as e:
            print(f"Error fetching '{query}' page {page}: {e}")
        time.sleep(2)  # avoid free-tier rate limits between calls
    return all_jobs


def is_recent(job: dict, days_back: int = 1) -> bool:
    """Keep jobs posted within the last `days_back` days (yesterday + today's overlap)."""
    posted_ts = job.get("job_posted_at_timestamp")
    if not posted_ts:
        return True  # keep if unknown rather than silently drop
    posted_dt = datetime.utcfromtimestamp(posted_ts)
    cutoff = datetime.utcnow() - timedelta(days=days_back + 1)
    return posted_dt >= cutoff


def is_relevant_location(job: dict) -> bool:
    """Keep jobs in India or fully remote. Falls back to text match if country field is missing."""
    country = (job.get("job_country") or "").upper()
    is_remote = job.get("job_is_remote", False)
    if country == "IN" or is_remote:
        return True
    # Fallback: some listings leave job_country blank - check location text fields
    text_blob = " ".join([
        job.get("job_city") or "",
        job.get("job_state") or "",
        job.get("job_location") or "",
    ]).lower()
    return "india" in text_blob


def dedupe(jobs: list) -> list:
    seen = set()
    unique = []
    for job in jobs:
        key = job.get("job_apply_link") or job.get("job_id")
        if key and key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def build_email_html(jobs: list) -> str:
    if not jobs:
        return "<p>No new matching jobs found for yesterday. Check back tomorrow!</p>"

    rows = []
    for job in jobs:
        title = job.get("job_title", "N/A")
        company = job.get("employer_name", "N/A")
        location = job.get("job_city") or ("Remote" if job.get("job_is_remote") else job.get("job_country", ""))
        link = job.get("job_apply_link", "#")
        posted_ts = job.get("job_posted_at_timestamp")
        posted = datetime.utcfromtimestamp(posted_ts).strftime("%d %b %Y") if posted_ts else "N/A"
        source = job.get("job_publisher", "N/A")

        rows.append(f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            <a href="{link}" style="font-weight:bold;color:#0a66c2;text-decoration:none;">{title}</a><br>
            <span style="color:#555;">{company} &middot; {location}</span><br>
            <span style="font-size:12px;color:#999;">Posted: {posted} | Source: {source}</span>
          </td>
        </tr>
        """)

    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;">
        <h2>Your Android/App Developer Job Digest</h2>
        <p>{len(jobs)} new job(s) found for yesterday across India & Remote.</p>
        <table style="width:100%;border-collapse:collapse;">
          {''.join(rows)}
        </table>
      </body>
    </html>
    """


def send_email(html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Android Dev Job Alert - {datetime.now().strftime('%d %b %Y')}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())


def main():
    all_jobs = []
    for query in SEARCH_QUERIES:
        print(f"Searching: {query}")
        all_jobs.extend(fetch_jobs_for_query(query))

    recent_jobs = [j for j in all_jobs if is_recent(j)]
    location_matched = [j for j in recent_jobs if is_relevant_location(j)]
    unique_jobs = dedupe(location_matched)

    print(f"Total raw jobs fetched (all queries): {len(all_jobs)}")
    print(f"After date/recency filter: {len(recent_jobs)}")
    print(f"After India/Remote location filter: {len(location_matched)}")
    print(f"After dedupe: {len(unique_jobs)}")

    html = build_email_html(unique_jobs)
    send_email(html)
    print("Email sent.")


if __name__ == "__main__":
    main()

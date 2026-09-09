import os
import time
import smtplib
import html
import requests

from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ============================================================
# CONFIG
# ============================================================

SEARCH_QUERIES = [
    "Android Developer",
    "Kotlin Android Developer",
    "Mobile Application Developer",
    "Android App Developer",
]

# JSearch experience filter
# Options:
#   no_experience
#   under_3_years_experience
#   more_than_3_years_experience
#
# Keep None if you want broader results.
EXPERIENCE_FILTER = "under_3_years_experience"

# JSearch supports:
# all, today, 3days, week, month
DATE_POSTED_BUCKET = "3days"

# Number of pages per query
PAGES_PER_QUERY = 1

# India
COUNTRY = "in"


# ============================================================
# ENVIRONMENT
# ============================================================

RAPIDAPI_KEY = os.environ["RAPIDAPI_KEY"]
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]
TO_EMAIL = os.environ["TO_EMAIL"]


# ============================================================
# JSEARCH
# ============================================================

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


def fetch_jobs_for_query(query: str):
    """
    Fetch jobs from JSearch.

    JSearch handles:
      - India
      - recently posted jobs
      - experience level
    """

    all_jobs = []

    for page in range(1, PAGES_PER_QUERY + 1):

        params = {
            "query": query,
            "page": page,
            "num_pages": 1,
            "date_posted": DATE_POSTED_BUCKET,
            "country": COUNTRY,
            "language": "en",
        }

        if EXPERIENCE_FILTER:
            params["job_requirements"] = EXPERIENCE_FILTER

        print()
        print("=" * 70)
        print(f"JSearch query: {query}")
        print(f"Parameters: {params}")
        print("=" * 70)

        try:

            response = requests.get(
                JSEARCH_URL,
                headers=HEADERS,
                params=params,
                timeout=30
            )

            print(f"HTTP status: {response.status_code}")

            if response.status_code != 200:

                print(
                    f"JSearch ERROR: "
                    f"{response.status_code} - "
                    f"{response.text[:1000]}"
                )

                continue

            data = response.json()

            jobs = data.get("data", [])

            print(
                f"JSearch returned {len(jobs)} jobs "
                f"for '{query}'"
            )

            for job in jobs:

                print(
                    f"  - {job.get('job_title')} | "
                    f"{job.get('employer_name')} | "
                    f"{job.get('job_posted_at')}"
                )

            all_jobs.extend(jobs)

        except requests.RequestException as e:

            print(
                f"Request failed for '{query}': {e}"
            )

        time.sleep(2)

    return all_jobs


# ============================================================
# DATE FILTER
# ============================================================

def is_recent(job: dict, days_back: int = 2) -> bool:
    """
    Keep jobs posted within the last `days_back` days.

    We use a small safety window because job boards can have
    slightly different timestamps.
    """

    posted_ts = job.get("job_posted_at_timestamp")

    if not posted_ts:
        return True

    try:

        posted_dt = datetime.fromtimestamp(
            int(posted_ts),
            tz=timezone.utc
        )

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=days_back
        )

        return posted_dt >= cutoff

    except (ValueError, TypeError, OverflowError):

        return True


# ============================================================
# RELEVANCE FILTER
# ============================================================

def is_relevant_job(job: dict) -> bool:
    """
    Final keyword filter.

    This prevents unrelated jobs such as:
      Software Engineer
      Java Developer
      UX Designer
      .NET Developer
    from appearing in the Android digest.
    """

    title = (job.get("job_title") or "").lower()

    description = (
        job.get("job_description") or ""
    ).lower()

    text = f"{title} {description}"

    # Android-specific keywords
    android_keywords = [
        "android developer",
        "android engineer",
        "android application",
        "android app",
        "android mobile",
        "kotlin android",
        "android development",
    ]

    # Mobile-specific keywords
    mobile_keywords = [
        "mobile application developer",
        "mobile app developer",
        "mobile developer",
        "mobile engineer",
    ]

    return (
        any(keyword in title for keyword in android_keywords)
        or any(keyword in title for keyword in mobile_keywords)
        or (
            "android" in title
            and (
                "developer" in title
                or "engineer" in title
            )
        )
    )


# ============================================================
# LOCATION FILTER
# ============================================================

def is_relevant_location(job: dict) -> bool:

    country = (
        job.get("job_country") or ""
    ).upper()

    is_remote = bool(
        job.get("job_is_remote", False)
    )

    if country == "IN":
        return True

    if is_remote:
        return True

    text_blob = " ".join([
        job.get("job_city") or "",
        job.get("job_state") or "",
        job.get("job_location") or "",
    ]).lower()

    return "india" in text_blob


# ============================================================
# DEDUPE
# ============================================================

def dedupe(jobs: list) -> list:

    seen = set()
    unique = []

    for job in jobs:

        key = (
            job.get("job_apply_link")
            or job.get("job_id")
            or job.get("job_title")
        )

        if key and key not in seen:

            seen.add(key)
            unique.append(job)

    return unique


# ============================================================
# EMAIL HTML
# ============================================================

def build_email_html(jobs: list) -> str:

    if not jobs:

        return """
        <html>
        <body style="font-family:Arial,sans-serif;">

            <h2>Android Developer Job Digest</h2>

            <p>
                No new matching Android jobs found
                in the selected period.
            </p>

            <p>
                Search source: JSearch
            </p>

        </body>
        </html>
        """

    rows = []

    for job in jobs:

        title = html.escape(
            job.get("job_title") or "N/A"
        )

        company = html.escape(
            job.get("employer_name") or "N/A"
        )

        city = job.get("job_city")

        if city:
            location = city

        elif job.get("job_is_remote"):
            location = "Remote"

        else:
            location = (
                job.get("job_location")
                or job.get("job_country")
                or "N/A"
            )

        location = html.escape(location)

        link = html.escape(
            job.get("job_apply_link") or "#",
            quote=True
        )

        posted_ts = job.get(
            "job_posted_at_timestamp"
        )

        if posted_ts:

            try:

                posted = datetime.fromtimestamp(
                    int(posted_ts),
                    tz=timezone.utc
                ).strftime("%d %b %Y")

            except Exception:

                posted = "N/A"

        else:

            posted = (
                job.get("job_posted_at")
                or "N/A"
            )

        source = html.escape(
            job.get("job_publisher") or "N/A"
        )

        rows.append(
            f"""
            <tr>
                <td style="
                    padding:12px;
                    border-bottom:1px solid #eee;
                ">

                    <a
                        href="{link}"
                        style="
                            font-weight:bold;
                            color:#0a66c2;
                            text-decoration:none;
                        "
                    >
                        {title}
                    </a>

                    <br>

                    <span style="color:#555;">
                        {company} &middot; {location}
                    </span>

                    <br>

                    <span style="
                        font-size:12px;
                        color:#999;
                    ">
                        Posted: {posted}
                        |
                        Source: {source}
                    </span>

                </td>
            </tr>
            """
        )

    return f"""
    <html>

    <body style="
        font-family:Arial,sans-serif;
        max-width:800px;
        margin:auto;
    ">

        <h2>
            Android Developer Job Digest
        </h2>

        <p>
            <b>{len(jobs)}</b>
            matching job(s) found.
        </p>

        <table style="
            width:100%;
            border-collapse:collapse;
        ">

            {''.join(rows)}

        </table>

    </body>

    </html>
    """


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(html_body: str):

    msg = MIMEMultipart("alternative")

    msg["Subject"] = (
        "Android Developer Job Alert - "
        f"{datetime.now().strftime('%d %b %Y')}"
    )

    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    msg.attach(
        MIMEText(
            html_body,
            "html"
        )
    )

    print("Connecting to Gmail SMTP...")

    with smtplib.SMTP(
        "smtp.gmail.com",
        587
    ) as server:

        server.starttls()

        print("Logging into Gmail...")

        server.login(
            EMAIL_ADDRESS,
            EMAIL_APP_PASSWORD
        )

        server.sendmail(
            EMAIL_ADDRESS,
            TO_EMAIL,
            msg.as_string()
        )

    print("Email sent successfully.")


# ============================================================
# MAIN
# ============================================================

def main():

    all_jobs = []

    for query in SEARCH_QUERIES:

        jobs = fetch_jobs_for_query(query)

        all_jobs.extend(jobs)

    print()
    print("=" * 70)
    print("FILTERING RESULTS")
    print("=" * 70)

    print(
        f"Total raw jobs fetched: "
        f"{len(all_jobs)}"
    )

    # Date
    recent_jobs = [
        job
        for job in all_jobs
        if is_recent(job)
    ]

    print(
        f"After date filter: "
        f"{len(recent_jobs)}"
    )

    # Location
    location_jobs = [
        job
        for job in recent_jobs
        if is_relevant_location(job)
    ]

    print(
        f"After India/Remote filter: "
        f"{len(location_jobs)}"
    )

    # Android relevance
    relevant_jobs = [
        job
        for job in location_jobs
        if is_relevant_job(job)
    ]

    print(
        f"After Android relevance filter: "
        f"{len(relevant_jobs)}"
    )

    # Deduplicate
    unique_jobs = dedupe(
        relevant_jobs
    )

    print(
        f"After dedupe: "
        f"{len(unique_jobs)}"
    )

    print()

    for job in unique_jobs:

        print(
            f"FINAL JOB: "
            f"{job.get('job_title')} | "
            f"{job.get('employer_name')}"
        )

    html = build_email_html(
        unique_jobs
    )

    send_email(html)


if __name__ == "__main__":
    main()

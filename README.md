# Daily Android Developer Job Alert

Automatically emails you a digest of new Android/App/Mobile Developer jobs
posted "yesterday" across India and Remote — sourced from LinkedIn, Naukri,
Indeed, Glassdoor, and company career pages via the JSearch API.

Runs for free every day using GitHub Actions — no server needed.

## Setup (one-time, ~10 minutes)

### 1. Get a JSearch API key (free tier)
1. Go to https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
2. Sign up / log in to RapidAPI.
3. Subscribe to the **free plan** (check current quota on the page — free tiers
   change over time, so verify the request limit fits a daily run of ~5 queries).
4. Copy your API key from the "X-RapidAPI-Key" field shown in the code snippets tab.

### 2. Create a Gmail App Password
1. Go to your Google Account → Security → 2-Step Verification (must be enabled).
2. Search for "App Passwords" → create one for "Mail".
3. Copy the 16-character password generated (not your normal Gmail password).

### 3. Create a GitHub repo and upload these files
1. Create a new **private** GitHub repository.
2. Upload `job_alert.py` and the `.github/workflows/daily-job-alert.yml` file
   (keep the folder structure — GitHub Actions looks for workflows in
   `.github/workflows/`).

### 4. Add your secrets
In your repo: Settings → Secrets and variables → Actions → New repository secret.
Add these four:
| Secret name | Value |
|---|---|
| `RAPIDAPI_KEY` | Your JSearch API key from step 1 |
| `EMAIL_ADDRESS` | The Gmail address that will send the email |
| `EMAIL_APP_PASSWORD` | The app password from step 2 |
| `TO_EMAIL` | The email address you want the digest sent to |

### 5. Test it
Go to the "Actions" tab in your repo → "Daily Android Job Alert" → "Run workflow"
button (this uses the `workflow_dispatch` trigger) to send yourself a test email
immediately, without waiting for the schedule.

### 6. Done
It will now run automatically every day at 08:30 AM IST (edit the cron line in
the workflow file to change the time — cron times are in UTC).

## Customizing

Open `job_alert.py` and edit the `SEARCH_QUERIES` list at the top to change
keywords, or `EXPERIENCE_FILTER` to adjust seniority. You can also add more
cities explicitly (e.g. `"Android Developer in Bangalore"`) if you want to
weight certain locations, alongside the broader "in India" / "Remote" queries.

## Notes & limitations

- **Free tier limits**: RapidAPI's JSearch free tier has a monthly request cap.
  Running 5 queries/day uses ~150/month — check current limits before relying
  on this daily, and upgrade if you add more keywords or run into rate limits.
- **"Yesterday" filtering**: JSearch's `date_posted` parameter supports
  `today`/`3days`/`week`/`month` buckets rather than an exact "yesterday" filter,
  so the script requests `today` and then filters by exact timestamp in code
  to approximate a rolling last-1-day window. If you run this early morning IST,
  most of what shows up will be genuinely from the previous day (US/Europe
  postings) plus overnight India postings.
- **Coverage**: JSearch aggregates from LinkedIn, Indeed, Naukri, Glassdoor,
  and others, but no aggregator has 100% coverage of every company career page.
  For maximum coverage you could add specific company career-page RSS feeds
  later, but this covers the large majority of postings.

# 🚀 Going Live with Real Data - Complete Guide

This guide walks you through collecting REAL franchise leads from Reddit, YouTube, and RSS feeds.

---

## 📋 Quick Overview

```
Step 1: Set up API credentials (5 mins)
Step 2: Test with small ingestion (2 mins)
Step 3: Run full ingestion (10-30 mins depending on data volume)
Step 4: Score and review leads (5 mins)
Step 5: Export to your CRM (1 min)
```

---

## 🔑 Step 1: Set Up API Credentials

### Reddit API (REQUIRED - Free)

Follow the detailed guide:
```bash
cat REDDIT_SETUP.md
```

**Quick version:**
1. Go to: https://www.reddit.com/prefs/apps
2. Create app, select "script" type
3. Copy CLIENT_ID and CLIENT_SECRET
4. Edit `.env` and add them:
   ```bash
   nano .env
   ```

### YouTube API (OPTIONAL - Free with limits)

1. Go to: https://console.cloud.google.com/
2. Create a new project
3. Enable "YouTube Data API v3"
4. Create credentials → API Key
5. Add to `.env`:
   ```bash
   YOUTUBE_API_KEY=your_key_here
   ```

### RSS Feeds (NO API KEY NEEDED)

RSS feeds work immediately, no setup required!

---

## 🧪 Step 2: Test with Small Ingestion

Let's test Reddit with a small batch first:

```bash
# Clear demo data (optional)
./radar demo clear

# Test Reddit ingestion (last 24 hours, max 20 posts)
./radar ingest --source reddit --since 24h --limit 20
```

**Expected output:**
```
Starting ingestion from reddit...
Ingesting from r/Entrepreneur
Ingesting from r/franchise
Fetched 12 documents from r/Entrepreneur
Fetched 8 documents from r/franchise
✓ Ingested 18 new documents
```

If you see this, it's working! ✅

---

## 🔄 Step 3: Run Full Ingestion

Now let's collect real data:

### Option A: Conservative (Recommended for first run)

```bash
# Reddit: Last 7 days
./radar ingest --source reddit --since 7d

# RSS: All configured feeds
./radar ingest --source rss

# YouTube: Last 7 days (if API key configured)
./radar ingest --source youtube --since 7d
```

**Estimated time:** 10-20 minutes (Reddit rate limits apply)

### Option B: Aggressive (More data)

```bash
# Reddit: Last 30 days, more posts
./radar ingest --source reddit --since 30d --limit 500

# RSS: All feeds
./radar ingest --source rss

# YouTube: Last 30 days
./radar ingest --source youtube --since 30d
```

**Estimated time:** 30-60 minutes

### Monitor Progress

Open another terminal and watch the database grow:
```bash
watch -n 5 'sqlite3 data/franchise_radar.db "SELECT COUNT(*) FROM documents;"'
```

---

## 🎯 Step 4: Score and Create Leads

Once ingestion completes, score the documents:

```bash
# Score all unprocessed documents
./radar score --type all --min-score 40
```

**What this does:**
1. Analyzes each document for franchise buyer signals (Type A)
2. Analyzes each document for gym owner pain signals (Type B)
3. Extracts location, budget, timeline hints
4. Deduplicates similar documents into canonical leads
5. Creates evidence records with scoring explanations

**Expected output:**
```
Starting scoring...
Processing 234 documents...
Scoring... ━━━━━━━━━━━━━━━━━━━━ 100% 0:00:45

Creating 67 franchise buyer leads...
Creating 31 owner pain leads...

✓ Created 67 buyer leads
✓ Created 31 owner pain leads
```

---

## 📊 Step 5: Review Your Leads

### View High-Quality Florida Leads

```bash
./radar list-leads --florida-only --min-score 70 --limit 20
```

### Filter by Lead Type

```bash
# Franchise buyers only
./radar list-leads --lead-type A --min-score 65

# Gym owners with problems only
./radar list-leads --lead-type B --min-score 65
```

### Export to CSV

```bash
# All high-quality leads
./radar export csv --output leads_$(date +%Y%m%d).csv --min-score 70

# HubSpot format
./radar export hubspot --output hubspot_import.csv --min-score 65 --florida-only

# Airtable format
./radar export airtable --output airtable_import.json --min-score 70
```

---

## 🌐 Step 6: Use the Web UI

Start the visual interface:

```bash
./run-ui.sh
```

Open in browser: **http://localhost:8000**

Features:
- 📊 Dashboard with statistics
- 🔍 Advanced filtering
- 📝 Lead details with evidence
- 🔗 Direct links to original posts
- 📤 One-click CSV export
- 📈 Scoring breakdown for each lead

---

## 📅 Daily Workflow (Once Set Up)

Create a script for daily updates:

```bash
#!/bin/bash
# daily_update.sh

echo "🔄 Running daily lead update..."

# Ingest new data
./radar ingest --source reddit --since 24h
./radar ingest --source rss
./radar ingest --source youtube --since 24h

# Score new documents
./radar score --type all --min-score 40

# Export top leads
./radar export csv \
  --output "leads_daily_$(date +%Y%m%d).csv" \
  --min-score 70 \
  --florida-only

echo "✅ Daily update complete!"
echo "📊 Check leads_daily_$(date +%Y%m%d).csv"
```

Make it executable:
```bash
chmod +x daily_update.sh
```

Run daily:
```bash
./daily_update.sh
```

Or automate with cron:
```bash
# Run every day at 8 AM
crontab -e
# Add: 0 8 * * * cd /home/user/franchise && ./daily_update.sh
```

---

## 🎛️ Customization

### Edit Subreddits to Monitor

```bash
nano config/general_gym_franchise.yaml
```

Find the `reddit:` section and add/remove subreddits:
```yaml
sources:
  reddit:
    subreddits:
      - Entrepreneur
      - smallbusiness
      - franchise
      - franchising
      - FitnessEntrepreneur
      - GymOwners
      # Add your own:
      - yoursubreddit
```

### Adjust Scoring Thresholds

In the same config file:
```yaml
scoring:
  thresholds:
    buyer_researching: 40    # Lower = more leads
    buyer_comparing: 60
    buyer_ready: 80
    owner_mild_pain: 40
    owner_serious_pain: 60
    owner_urgent: 80
```

### Add Custom Keywords

Add to phrase_packs:
```yaml
phrase_packs:
  franchise_buyer_high:
    - phrase: "your custom phrase"
      weight: 8
```

---

## 📈 Expected Results

### First 7-Day Run:
- **Documents ingested:** 200-500
- **Franchise buyer leads (Type A):** 30-80
- **Owner pain leads (Type B):** 20-60
- **Florida-specific leads:** 10-30
- **High-quality (score >70):** 15-40

### After 30 Days:
- **Total leads:** 150-300+
- **High-quality pipeline:** 50-100 leads

---

## ⚠️ Important Notes

### Rate Limits
- **Reddit:** 60 requests/min (built-in handling)
- **YouTube:** 10,000 units/day (generous)
- **RSS:** No limits

### Storage
- SQLite database grows ~1-2 MB per 1000 documents
- No performance issues up to 100k documents

### Compliance
- ✅ Only public data
- ✅ Respects robots.txt
- ✅ Uses official APIs
- ✅ No login scraping
- ✅ Rate limiting built-in

---

## 🐛 Troubleshooting

### "No documents ingested"
- Check API credentials in `.env`
- Verify subreddits exist and are public
- Try increasing `--limit`

### "Score is 0 for all leads"
- Check if phrase packs loaded: `cat config/general_gym_franchise.yaml`
- Verify documents have content: `sqlite3 data/franchise_radar.db "SELECT title FROM documents LIMIT 5;"`

### "Too slow"
- Normal for first run (Reddit rate limits)
- Subsequent runs are faster (only new data)
- Consider running overnight for large batches

---

## ✅ You're Live!

Once you've completed these steps:
1. ✅ API credentials configured
2. ✅ Data ingested
3. ✅ Leads scored and reviewed
4. ✅ Exports generated

You now have a **working lead generation system** finding real franchise opportunities and struggling gym owners!

Run this daily or weekly to keep your pipeline full.

---

## 📞 Quick Commands Reference

```bash
# Status check
./radar list-leads --limit 5

# Full refresh
./radar ingest --source reddit --since 7d
./radar score --type all

# Export best leads
./radar export hubspot --output export.csv --min-score 70

# Web UI
./run-ui.sh
```

**Happy lead hunting! 🎯**

# Franchise Lead Radar - Usage Guide

## 📦 Installation & Setup

### Step 1: Install Dependencies

```bash
cd /home/user/franchise

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install package
pip install -e .
```

### Step 2: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit with your API keys (optional for demo mode)
nano .env
```

### Step 3: Initialize Database

```bash
# Initialize SQLite database
python -m franchise_radar init
```

**Expected output:**
```
Database initialized successfully
```

---

## 🎮 Running Demo Mode (No API Keys Required)

Perfect for testing immediately!

### Create Demo Data

```bash
python -m franchise_radar demo create --count 10
```

**Expected output:**
```
Creating 10 demo leads...
✓ Created 10 demo leads

Try these commands:
  python -m franchise_radar list-leads
  python -m franchise_radar export csv --output demo_leads.csv
```

### View Demo Leads

```bash
python -m franchise_radar list-leads --limit 10
```

**Expected output:**
```
┏━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┓
┃ ID  ┃ Type ┃ Handle                ┃ Location    ┃ Score ┃ Tier     ┃ Status  ┃
┡━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━┩
│ 1   │ A    │ fitness_entrepren... │ Miami, FL   │ 87.3  │ Ready    │ new     │
│ 2   │ B    │ tampa_gym_owner      │ Tampa, FL   │ 76.5  │ Urgent   │ new     │
└─────┴──────┴──────────────────────┴─────────────┴───────┴──────────┴─────────┘
```

### Export Demo Data

```bash
# Export to CSV
python -m franchise_radar export csv --output demo_leads.csv

# Export HubSpot format
python -m franchise_radar export hubspot --output hubspot_import.csv --min-score 60

# Export Airtable format
python -m franchise_radar export airtable --output airtable_import.json
```

### Start Web UI

```bash
# Using Makefile
make run-ui

# Or directly with uvicorn
uvicorn franchise_radar.api.app:app --reload --host 0.0.0.0 --port 8000
```

Then open: **http://localhost:8000**

### Clear Demo Data

```bash
python -m franchise_radar demo clear
```

---

## 🚀 Production Usage (With API Keys)

### Reddit Ingestion

```bash
# Ingest from last 24 hours
python -m franchise_radar ingest --source reddit --since 24h

# Ingest from last 7 days
python -m franchise_radar ingest --source reddit --since 7d --limit 500
```

**Expected output:**
```
Starting ingestion from reddit...
Ingesting from r/Entrepreneur
Ingesting from r/franchise
Fetched 45 documents from r/Entrepreneur
✓ Ingested 127 new documents
```

### RSS Ingestion

```bash
# Ingest all configured RSS feeds
python -m franchise_radar ingest --source rss
```

**Expected output:**
```
Starting ingestion from rss...
Fetching RSS feed: Franchise Gator
Fetching RSS feed: Entrepreneur Franchises
✓ Ingested 34 new documents
```

### YouTube Ingestion

```bash
# Ingest videos from last 7 days
python -m franchise_radar ingest --source youtube --since 7d
```

**Expected output:**
```
Starting ingestion from youtube...
Searching YouTube for: buy gym franchise
Searching YouTube for: gym franchise opportunities
✓ Ingested 52 new documents
```

### Web Crawling

```bash
# Create seeds file
cat > seeds.txt << EOF
https://www.franchisegator.com/franchises/fitness/
https://www.entrepreneur.com/franchises/fitness
EOF

# Crawl seed URLs
python -m franchise_radar ingest --source web_crawl --seeds seeds.txt --limit 100
```

**Expected output:**
```
Starting ingestion from web_crawl...
Crawling https://www.franchisegator.com/franchises/fitness/
✓ Ingested 23 new documents
```

### Score Documents & Create Leads

```bash
# Score all unprocessed documents
python -m franchise_radar score --type all --min-score 40
```

**Expected output:**
```
Starting scoring...
Processing 127 documents...
Scoring... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:15

Creating 34 franchise buyer leads...
Creating 18 owner pain leads...

✓ Created 34 buyer leads
✓ Created 18 owner pain leads
```

### Filter & View Leads

```bash
# Florida leads only, high score
python -m franchise_radar list-leads --florida-only --min-score 70

# Franchise buyers only
python -m franchise_radar list-leads --lead-type A --limit 20

# All owner pain leads
python -m franchise_radar list-leads --lead-type B
```

---

## 📥 Manual Import

### Generate Import Template

```bash
# CSV template
python -m franchise_radar config-template --output my_import.csv --format csv

# JSON template
python -m franchise_radar config-template --output my_import.json --format json
```

### CSV Format

```csv
url,handle,title,body,published_at,context
https://example.com/post1,john_doe,Looking for gym franchise,I'm interested in buying a gym franchise in Miami. Budget around $200k.,2024-01-15T10:00:00,"{\"platform\": \"quora\"}"
```

### Import Data

```bash
# Import CSV
python -m franchise_radar import my_import.csv --source-name quora_exports

# Import JSON
python -m franchise_radar import my_import.json --source-name linkedin_posts
```

**Expected output:**
```
Importing from my_import.csv...
✓ Imported 25 documents
```

Then score the imported data:

```bash
python -m franchise_radar score --type all
```

---

## 📊 API Usage

### Start API Server

```bash
uvicorn franchise_radar.api.app:app --host 0.0.0.0 --port 8000
```

### API Endpoints

#### Get Leads
```bash
# All leads
curl http://localhost:8000/api/leads

# Filter by type and score
curl "http://localhost:8000/api/leads?lead_type=A&min_score=70&limit=10"

# Florida leads only
curl "http://localhost:8000/api/leads?is_florida=true"
```

#### Get Lead Detail
```bash
curl http://localhost:8000/api/leads/1
```

Response:
```json
{
  "lead_id": 1,
  "lead_type": "A",
  "canonical_handle": "fitness_entrepreneur_123",
  "location_text": "Miami, FL",
  "priority_score": 87.3,
  "tier": "Ready",
  "evidence": [
    {
      "snippet": "I'm looking to buy a gym franchise...",
      "reasons": [
        "Found 5 franchise intent phrases",
        "First-person intent detected",
        "Location signals: Florida"
      ],
      "score": 87.3,
      "url": "https://reddit.com/r/Entrepreneur/comments/..."
    }
  ]
}
```

#### Update Lead Status
```bash
curl -X PATCH http://localhost:8000/api/leads/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "qualified", "note": "High potential buyer"}'
```

#### Get Statistics
```bash
curl http://localhost:8000/api/stats
```

#### Export CSV via API
```bash
curl "http://localhost:8000/api/export/csv?min_score=60" --output leads_export.csv
```

#### Upload Import File
```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@my_import.csv" \
  -F "source_name=manual"
```

---

## 🧪 Testing

### Run All Tests

```bash
make test
```

### Run Specific Test File

```bash
pytest tests/test_scoring.py -v
```

### Run with Coverage

```bash
pytest tests/ -v --cov=src/franchise_radar --cov-report=html
open htmlcov/index.html
```

---

## 📈 Complete Workflow Example

### Day 1: Initial Setup

```bash
# 1. Install
pip install -e .

# 2. Initialize
python -m franchise_radar init

# 3. Create demo data
python -m franchise_radar demo create --count 20

# 4. View in UI
make run-ui
```

### Day 2: Real Ingestion

```bash
# 1. Ingest from Reddit
python -m franchise_radar ingest --source reddit --since 7d

# 2. Ingest from YouTube
python -m franchise_radar ingest --source youtube --since 7d

# 3. Ingest from RSS
python -m franchise_radar ingest --source rss

# 4. Score everything
python -m franchise_radar score --type all --min-score 40
```

### Day 3: Review & Export

```bash
# 1. View top leads
python -m franchise_radar list-leads --florida-only --min-score 70 --limit 50

# 2. Export for HubSpot
python -m franchise_radar export hubspot --output hubspot_import.csv --min-score 65

# 3. Export for Airtable
python -m franchise_radar export airtable --output airtable_import.json --min-score 60

# 4. General CSV export
python -m franchise_radar export csv --output all_leads.csv --florida-only
```

---

## 🔄 Automated Workflow (Cron/Scheduled)

### Daily Ingestion Script

Create `daily_ingest.sh`:

```bash
#!/bin/bash
cd /home/user/franchise
source venv/bin/activate

# Ingest
python -m franchise_radar ingest --source reddit --since 24h
python -m franchise_radar ingest --source rss
python -m franchise_radar ingest --source youtube --since 24h

# Score
python -m franchise_radar score --type all --min-score 40

# Export top leads
python -m franchise_radar export csv \
  --output "data/exports/leads_$(date +%Y%m%d).csv" \
  --min-score 70 \
  --florida-only

echo "Daily ingestion complete: $(date)"
```

Make executable and add to crontab:

```bash
chmod +x daily_ingest.sh

# Run daily at 6am
crontab -e
# Add: 0 6 * * * /home/user/franchise/daily_ingest.sh >> /home/user/franchise/logs/cron.log 2>&1
```

---

## 🐛 Common Issues

### "Database not initialized"
```bash
python -m franchise_radar init
```

### "Reddit API not initialized"
Check `.env` file has correct credentials:
```bash
cat .env | grep REDDIT
```

### "No leads found"
1. Check if documents were ingested:
```bash
sqlite3 data/franchise_radar.db "SELECT COUNT(*) FROM documents;"
```

2. Check if documents were scored:
```bash
sqlite3 data/franchise_radar.db "SELECT COUNT(*) FROM documents WHERE processed = 1;"
```

3. Run scoring:
```bash
python -m franchise_radar score --type all --min-score 30
```

### "Module not found"
Reinstall in editable mode:
```bash
pip install -e .
```

---

## 📞 Support

- Check logs: `data/*.log` or console output
- Run tests: `make test`
- View database: `sqlite3 data/franchise_radar.db`
- API docs: http://localhost:8000/docs (when API is running)

---

**Happy lead hunting! 🎯**

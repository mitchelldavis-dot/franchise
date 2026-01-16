# 🚀 Franchise Lead Radar - Quick Start

**Get running in 30 seconds!**

## Already Set Up! ✅

The application is installed and demo data is loaded. Just use these commands:

### View Leads

```bash
./radar list-leads
```

### Export to CSV

```bash
./radar export csv --output leads.csv
```

### Export for HubSpot

```bash
./radar export hubspot --output hubspot_import.csv --min-score 60
```

### Export for Airtable

```bash
./radar export airtable --output airtable_import.json
```

### Start Web UI

```bash
./run-ui.sh
```

Then open: **http://localhost:8000**

---

## Available Commands

### Demo Commands

```bash
./radar demo create --count 20    # Create more demo leads
./radar demo clear                # Clear all demo data
```

### Lead Management

```bash
./radar list-leads                          # List all leads
./radar list-leads --florida-only           # Florida leads only
./radar list-leads --min-score 70           # High-scoring leads
./radar list-leads --lead-type A            # Franchise buyers only
./radar list-leads --lead-type B            # Owner pain leads only
```

### Data Ingestion (Requires API Keys)

```bash
# Set up API keys first
cp .env.example .env
nano .env  # Add your Reddit, YouTube keys

# Then ingest
./radar ingest --source reddit --since 7d
./radar ingest --source youtube --since 7d
./radar ingest --source rss

# Score the ingested data
./radar score --type all --min-score 40
```

### Manual Import

```bash
# Generate template
./radar config-template --output my_import.csv --format csv

# Edit the CSV file, then import
./radar import my_import.csv --source-name my_source

# Score the imported data
./radar score --type all
```

---

## File Locations

- **Database**: `data/franchise_radar.db`
- **Exports**: Any filename you specify
- **Config**: `config/general_gym_franchise.yaml` (edit to customize)
- **Logs**: Console output or add file logging as needed

---

## Next Steps

1. **Try the Web UI**: Run `./run-ui.sh` and explore the dashboard
2. **Customize Config**: Edit `config/general_gym_franchise.yaml` to add your own keywords
3. **Set Up API Keys**: Copy `.env.example` to `.env` and add credentials
4. **Run Real Ingestion**: Use `./radar ingest` commands to collect real data
5. **Export Leads**: Use export commands to get data into your CRM

---

## Need Help?

- **Full documentation**: See `README.md` and `USAGE.md`
- **Test the system**: Run `pytest tests/` (need to install dev dependencies)
- **Check database**: `sqlite3 data/franchise_radar.db`

---

**Happy lead hunting! 🎯**

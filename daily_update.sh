#!/bin/bash
# Daily Lead Update Script
# Run this daily to collect new leads

set -e  # Exit on error

echo "🔄 Starting daily lead update..."
echo "📅 $(date)"
echo ""

# Activate virtual environment
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Ingest new data from last 24 hours
echo "📥 Ingesting Reddit posts (last 24h)..."
./radar ingest --source reddit --since 24h

echo "📥 Ingesting RSS feeds..."
./radar ingest --source rss

# Uncomment if you have YouTube API key
# echo "📥 Ingesting YouTube videos (last 24h)..."
# ./radar ingest --source youtube --since 24h

# Score all new documents
echo ""
echo "🎯 Scoring new documents..."
./radar score --type all --min-score 40

# Export top leads
OUTPUT_FILE="exports/leads_daily_$(date +%Y%m%d).csv"
mkdir -p exports

echo ""
echo "📤 Exporting top leads to ${OUTPUT_FILE}..."
./radar export csv \
  --output "${OUTPUT_FILE}" \
  --min-score 70 \
  --florida-only

# Show summary
echo ""
echo "✅ Daily update complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Summary:"
./radar list-leads --florida-only --min-score 70 --limit 5

echo ""
echo "📁 Export saved to: ${OUTPUT_FILE}"
echo "🌐 View in UI: ./run-ui.sh"
echo ""

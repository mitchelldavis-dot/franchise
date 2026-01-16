# 🔑 How to Get Reddit API Credentials (Free)

## Step-by-Step Instructions:

1. **Go to Reddit Apps Page**
   - Visit: https://www.reddit.com/prefs/apps
   - Log in to your Reddit account (or create one if needed)

2. **Create a New App**
   - Scroll to the bottom
   - Click **"create another app..."** or **"are you a developer? create an app..."**

3. **Fill Out the Form**
   - **Name**: `Franchise Lead Radar`
   - **App type**: Select **"script"** (radio button)
   - **Description**: `Lead discovery tool for franchise opportunities`
   - **About URL**: Leave blank (optional)
   - **Redirect URI**: `http://localhost:8000` (required but not used)
   - Click **"create app"**

4. **Copy Your Credentials**

   After creating, you'll see:

   ```
   Franchise Lead Radar         script
   personal use script
   [14-character string]  <-- This is your CLIENT_ID

   secret    [27-character string]  <-- This is your CLIENT_SECRET
   ```

5. **Add to Your .env File**

   Open `.env` in a text editor:
   ```bash
   nano .env
   ```

   Replace these lines:
   ```bash
   REDDIT_CLIENT_ID=the_14_character_string_here
   REDDIT_CLIENT_SECRET=the_27_character_secret_here
   REDDIT_USER_AGENT=FranchiseRadar/0.1.0
   ```

   Save and exit (Ctrl+X, then Y, then Enter)

6. **Test It**
   ```bash
   ./radar ingest --source reddit --since 24h --limit 20
   ```

---

## 📝 Example .env Configuration

```bash
REDDIT_CLIENT_ID=AbCdEfGhIjKlMn
REDDIT_CLIENT_SECRET=XyZ123aBc456DeF789GhI012jKl
REDDIT_USER_AGENT=FranchiseRadar/0.1.0
```

---

## ⚠️ Important Notes

- **Free Tier Limits**: 60 requests per minute (plenty for our use)
- **Keep Secret**: Never commit your `.env` file to git (it's already in .gitignore)
- **Personal Use**: This is for personal/development use, perfect for this tool

---

## 🔍 Troubleshooting

**If you get "401 Unauthorized":**
- Double-check you selected "script" type (not "web app")
- Make sure you copied the CLIENT_ID and CLIENT_SECRET correctly
- Try regenerating the secret in Reddit settings

**If ingestion is slow:**
- This is normal! Reddit rate limits are 60 requests/min
- The tool has built-in rate limiting and retry logic
- Be patient on first run, it will work

---

## ✅ You're Ready!

Once configured, run:
```bash
./radar ingest --source reddit --since 7d
./radar score --type all --min-score 40
./radar list-leads --florida-only --min-score 70
```

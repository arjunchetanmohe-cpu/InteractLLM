import sqlite3
from datasets import load_dataset

# Use wikimedia/wikipedia (or "omarkamali/wikipedia-monthly" with "latest.en")
ds = load_dataset(
    "wikimedia/wikipedia",
    "20231101.en",
    split="train",
    streaming=True,
)

conn = sqlite3.connect("wiki_50k.db")
conn.execute(
    "CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, title TEXT, text TEXT, url TEXT)"
)

batch = []
count = 0
for row in ds:
    if count >= 50_000:
        break

    title = row.get("title") or ""
    text = row.get("text") or ""
    if not title or not text.strip():
        continue

    article_id = str(row.get("id", count))
    url = row.get("url", "")
    batch.append((article_id, title, text, url))
    count += 1

    if len(batch) >= 1000:
        conn.executemany(
            "INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?)", batch
        )
        conn.commit()
        batch.clear()
        print(f"Saved {count} / 50000 articles...")

if batch:
    conn.executemany(
        "INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?)", batch
    )
    conn.commit()

conn.close()
print(f"Done. Saved {count} articles to wiki_50k.db.")
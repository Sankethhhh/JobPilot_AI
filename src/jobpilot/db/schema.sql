CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL,
  role TEXT NOT NULL,
  country TEXT NOT NULL,
  match_score INTEGER NOT NULL,
  resume_path TEXT NOT NULL,
  cover_letter_text TEXT DEFAULT '',
  applied INTEGER DEFAULT 0,
  stage TEXT DEFAULT 'Applied',
  notes TEXT DEFAULT '',
  status_reason TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

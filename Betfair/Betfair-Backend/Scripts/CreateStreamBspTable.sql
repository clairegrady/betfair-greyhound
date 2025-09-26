-- Create StreamBspProjections table for storing BSP data from Stream API
CREATE TABLE IF NOT EXISTS StreamBspProjections (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    MarketId TEXT NOT NULL,
    SelectionId INTEGER NOT NULL,
    RunnerName TEXT,
    NearPrice REAL,
    FarPrice REAL,
    Average REAL,
    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(MarketId, SelectionId)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_streambsp_marketid ON StreamBspProjections(MarketId);
CREATE INDEX IF NOT EXISTS idx_streambsp_selectionid ON StreamBspProjections(SelectionId);

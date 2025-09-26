-- Create StreamLtpData table for storing LTP (Last Traded Price) data from Stream API
CREATE TABLE IF NOT EXISTS StreamLtpData (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    MarketId TEXT NOT NULL,
    SelectionId INTEGER NOT NULL,
    RunnerName TEXT,
    LastTradedPrice REAL,
    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(MarketId, SelectionId)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_streamltp_marketid ON StreamLtpData(MarketId);
CREATE INDEX IF NOT EXISTS idx_streamltp_selectionid ON StreamLtpData(SelectionId);

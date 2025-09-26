-- Test script to verify BSP and LTP data insertion
-- Insert test BSP data
INSERT OR REPLACE INTO StreamBspProjections
(MarketId, SelectionId, RunnerName, NearPrice, FarPrice, Average, UpdatedAt)
VALUES
('1.248149135', 59496578, 'Test Runner 1', 13.5, 6.48, 10.0, datetime('now'));

-- Insert test LTP data
INSERT OR REPLACE INTO StreamLtpData
(MarketId, SelectionId, RunnerName, LastTradedPrice, UpdatedAt)
VALUES
('1.248149135', 59496578, 'Test Runner 1', 17.5, datetime('now'));

-- Verify the data was inserted
SELECT 'BSP Data:' as DataType, COUNT(*) as Count FROM StreamBspProjections
UNION ALL
SELECT 'LTP Data:' as DataType, COUNT(*) as Count FROM StreamLtpData;

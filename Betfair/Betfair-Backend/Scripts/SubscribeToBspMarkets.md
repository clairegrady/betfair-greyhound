# How to Subscribe to Markets with SP_PROJECTED Field Filter

## Step 1: Connect to Stream API
```bash
curl -X POST http://localhost:5173/api/streamapi/connect
```

## Step 2: Subscribe to Markets with SP_PROJECTED Field Filter

### For Specific Market IDs:
```bash
curl -X POST "http://localhost:5173/api/streamapi/subscribe/market/1.123456789" \
  -H "Content-Type: application/json" \
  -d '{
    "marketFilter": {
      "marketIds": ["1.123456789"]
    },
    "marketDataFilter": {
      "fields": ["SP_PROJECTED", "EX_MARKET_DEF", "EX_BEST_OFFERS", "EX_LTP"]
    },
    "segmentationEnabled": true,
    "conflateMs": 0,
    "heartbeatMs": 5000
  }'
```

### For All Horse Racing Markets:
```bash
curl -X POST "http://localhost:5173/api/streamapi/subscribe/market/all" \
  -H "Content-Type: application/json" \
  -d '{
    "marketFilter": {
      "eventTypeIds": ["7"],
      "bspMarket": true,
      "turnInPlayEnabled": true
    },
    "marketDataFilter": {
      "fields": ["SP_PROJECTED", "EX_MARKET_DEF", "EX_BEST_OFFERS", "EX_LTP"]
    },
    "segmentationEnabled": true,
    "conflateMs": 0,
    "heartbeatMs": 5000
  }'
```

## Step 3: Check BSP Data
```bash
curl "http://localhost:5173/api/streamapi/bsp/1.123456789"
```

## Step 4: Monitor Stream API Status
```bash
curl "http://localhost:5173/api/streamapi/status"
```

## Field Filter Options for BSP:

### Essential Fields:
- `SP_PROJECTED` - BSP Near and Far prices
- `EX_MARKET_DEF` - Market definition
- `EX_BEST_OFFERS` - Best back/lay prices

### Optional Fields:
- `EX_BEST_OFFERS_DISP` - Best prices including virtual bets
- `EX_ALL_OFFERS` - Full price ladder
- `EX_TRADED` - Traded volume
- `EX_LTP` - Last traded price

## Example Market Subscription Message:
```json
{
  "op": "marketSubscription",
  "id": 1,
  "marketFilter": {
    "marketIds": ["1.123456789"],
    "bspMarket": true,
    "turnInPlayEnabled": true
  },
  "marketDataFilter": {
    "fields": ["SP_PROJECTED", "EX_MARKET_DEF", "EX_BEST_OFFERS"],
    "ladderLevels": 3
  },
  "segmentationEnabled": true,
  "conflateMs": 0,
  "heartbeatMs": 5000
}
```

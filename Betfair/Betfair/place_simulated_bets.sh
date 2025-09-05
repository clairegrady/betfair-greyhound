#!/bin/bash

# Wait for application to start
sleep 10

echo "🎯 Placing simulated bets for today's races..."

# Bet 1: Lemon Sohn in Race 2 at Canterbury Park
echo "Placing bet 1: Lemon Sohn (WIN)"
curl -X POST "http://localhost:5173/api/simulation/place-bet" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "1.246847916",
    "selectionId": 76119457,
    "stake": 15.0,
    "betType": "WIN",
    "predictedProbability": 0.28,
    "confidence": 0.75
  }'

echo -e "\n"

# Bet 2: Tygra in Race 2 at Canterbury Park
echo "Placing bet 2: Tygra (WIN)"
curl -X POST "http://localhost:5173/api/simulation/place-bet" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "1.246847916",
    "selectionId": 10189136,
    "stake": 10.0,
    "betType": "WIN",
    "predictedProbability": 0.22,
    "confidence": 0.65
  }'

echo -e "\n"

# Bet 3: Moral Dilemma in Race 2 at Canterbury Park
echo "Placing bet 3: Moral Dilemma (WIN)"
curl -X POST "http://localhost:5173/api/simulation/place-bet" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "1.246847916",
    "selectionId": 71023278,
    "stake": 20.0,
    "betType": "WIN",
    "predictedProbability": 0.35,
    "confidence": 0.85
  }'

echo -e "\n"

# Bet 4: Flat Out Blessed in Race 2 at Canterbury Park
echo "Placing bet 4: Flat Out Blessed (WIN)"
curl -X POST "http://localhost:5173/api/simulation/place-bet" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "1.246847916",
    "selectionId": 81814574,
    "stake": 12.0,
    "betType": "WIN",
    "predictedProbability": 0.18,
    "confidence": 0.60
  }'

echo -e "\n"

# Bet 5: Lazy Y Girvin in Race 2 at Canterbury Park
echo "Placing bet 5: Lazy Y Girvin (WIN)"
curl -X POST "http://localhost:5173/api/simulation/place-bet" \
  -H "Content-Type: application/json" \
  -d '{
    "marketId": "1.246847916",
    "selectionId": 85872043,
    "stake": 8.0,
    "betType": "WIN",
    "predictedProbability": 0.15,
    "confidence": 0.55
  }'

echo -e "\n"

echo "✅ All simulated bets placed! Checking current bets..."

# Check all bets
curl -X GET "http://localhost:5173/api/simulation/bets"

echo -e "\n"

# Check pending bets
curl -X GET "http://localhost:5173/api/simulation/bets/pending"

echo -e "\n"

# Get simulation summary
curl -X GET "http://localhost:5173/api/simulation/summary"

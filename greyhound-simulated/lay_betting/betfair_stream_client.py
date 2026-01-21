"""
Direct Betfair Stream API Consumer
Connects directly to Betfair's Stream API for real-time odds
Bypasses C# backend and PostgreSQL for maximum speed
"""
import json
import socket
import ssl
import threading
import time
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BetfairStreamClient:
    """Direct connection to Betfair Stream API for real-time odds"""
    
    def __init__(self, app_key: str, session_token: str):
        self.app_key = app_key
        self.session_token = session_token
        self.host = "stream-api.betfair.com"
        self.port = 443
        
        # In-memory cache of latest odds {market_id: {selection_id: {price, size, timestamp}}}
        self.market_data = {}
        self.market_definitions = {}  # Store runner names, etc
        
        self.socket = None
        self.connection_id = None
        self.running = False
        self.subscribed_markets = set()
        
    def connect(self):
        """Establish SSL connection to Stream API"""
        try:
            # Create SSL socket
            context = ssl.create_default_context()
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = context.wrap_socket(raw_socket, server_hostname=self.host)
            self.socket.connect((self.host, self.port))
            
            logger.info(f"🔌 Connected to {self.host}:{self.port}")
            
            # Read connection message
            response = self._read_message()
            if response and response.get('op') == 'connection':
                self.connection_id = response.get('connectionId')
                logger.info(f"✅ Connection ID: {self.connection_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def authenticate(self):
        """Authenticate with Betfair"""
        try:
            auth_message = {
                "op": "authentication",
                "id": 1,
                "appKey": self.app_key,
                "session": self.session_token
            }
            
            self._send_message(auth_message)
            response = self._read_message()
            
            if response and response.get('statusCode') == 'SUCCESS':
                logger.info("✅ Authenticated successfully")
                return True
            else:
                logger.error(f"❌ Authentication failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False
    
    def subscribe_to_market(self, market_id: str):
        """Subscribe to a specific market for real-time updates"""
        try:
            if market_id in self.subscribed_markets:
                return True
            
            subscribe_message = {
                "op": "marketSubscription",
                "id": 2,
                "marketIds": [market_id],
                "marketDataFilter": {
                    "fields": ["EX_BEST_OFFERS", "EX_MARKET_DEF"],
                    "ladderLevels": 3  # Get top 3 price levels
                }
            }
            
            self._send_message(subscribe_message)
            
            # Don't wait for response - it comes asynchronously
            self.subscribed_markets.add(market_id)
            logger.info(f"📡 Subscribed to market: {market_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Subscribe error: {e}")
            return False
    
    def start_listening(self):
        """Start listening thread for incoming messages"""
        self.running = True
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
        logger.info("🎧 Started listening thread")
    
    def _listen_loop(self):
        """Main loop to receive and process messages"""
        while self.running:
            try:
                message = self._read_message()
                if message:
                    self._process_message(message)
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                time.sleep(1)
    
    def _process_message(self, message: dict):
        """Process incoming Stream API messages"""
        op = message.get('op')
        
        if op == 'mcm':  # Market Change Message
            for mc in message.get('mc', []):
                market_id = mc.get('id')
                
                # Store market definition (runner names, etc)
                if 'marketDefinition' in mc:
                    self.market_definitions[market_id] = mc['marketDefinition']
                
                # Process runner changes (odds)
                for rc in mc.get('rc', []):
                    selection_id = rc.get('id')
                    
                    # Get lay prices (batl = Best Available To Lay)
                    batl = rc.get('batl', [])
                    if batl:
                        if market_id not in self.market_data:
                            self.market_data[market_id] = {}
                        
                        # batl format: [[level, price, size], [level, price, size], ...]
                        best_lay = batl[0] if batl else None
                        if best_lay and len(best_lay) >= 3:
                            self.market_data[market_id][selection_id] = {
                                'price': best_lay[1],  # Price is at index 1
                                'size': best_lay[2],   # Size is at index 2
                                'timestamp': datetime.now(),
                                'level': best_lay[0]   # Level is at index 0
                            }
                            
                            logger.debug(f"💰 {market_id} | Runner {selection_id} | Lay @ {best_lay[1]} (${best_lay[2]})")
        
        elif op == 'status':
            status = message.get('statusCode')
            if status != 'SUCCESS':
                logger.warning(f"⚠️  Status: {message}")
    
    def get_market_odds(self, market_id: str) -> Optional[Dict]:
        """Get latest odds for a market from in-memory cache"""
        if market_id not in self.market_data:
            return None
        
        runners = []
        market_def = self.market_definitions.get(market_id, {})
        runner_defs = {r['id']: r for r in market_def.get('runners', [])}
        
        for selection_id, data in self.market_data[market_id].items():
            runner_def = runner_defs.get(selection_id, {})
            
            runners.append({
                'selection_id': selection_id,
                'odds': data['price'],
                'size': data['size'],
                'dog_name': runner_def.get('name', f'Dog {selection_id}'),
                'box': runner_def.get('sortPriority'),
                'timestamp': data['timestamp']
            })
        
        return {'runners': runners} if runners else None
    
    def _send_message(self, message: dict):
        """Send JSON message to Stream API"""
        message_str = json.dumps(message) + '\r\n'
        self.socket.sendall(message_str.encode('utf-8'))
    
    def _read_message(self) -> Optional[dict]:
        """Read and parse JSON message from Stream API"""
        try:
            buffer = b''
            while b'\r\n' not in buffer:
                chunk = self.socket.recv(4096)
                if not chunk:
                    return None
                buffer += chunk
            
            message_str = buffer.split(b'\r\n')[0].decode('utf-8')
            return json.loads(message_str)
            
        except Exception as e:
            logger.error(f"Error reading message: {e}")
            return None
    
    def disconnect(self):
        """Close connection"""
        self.running = False
        if self.socket:
            self.socket.close()
        logger.info("🔌 Disconnected from Stream API")

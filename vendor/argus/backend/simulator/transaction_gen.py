"""
ARGUS Transaction Generator v3.0.0-india
=========================================
Realistic Indian payment transaction simulator.
Generates logically consistent data for UPI, Cards, NetBanking, Wallets, ATM.

Key Logic:
- ATM = Cash Withdrawal ONLY (₹100-25K, multiples of ₹100)
- UPI = P2P, QR payments, bill pay (₹1-1L)
- POS = Physical card swipes (₹50-50K)
- CARD_ONLINE = E-commerce (₹100-2L)
- NETBANKING = High value transfers, EMI (₹500-10L)
- WALLET = Small payments (₹1-10K)
"""

import random
import uuid
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# ============ INDIAN CITIES ============

INDIAN_CITIES = [
    # Tier 1 (40% of transactions)
    {'name': 'Mumbai', 'state': 'MH', 'tier': 1, 'weight': 0.15},
    {'name': 'Delhi', 'state': 'DL', 'tier': 1, 'weight': 0.12},
    {'name': 'Bangalore', 'state': 'KA', 'tier': 1, 'weight': 0.10},
    {'name': 'Chennai', 'state': 'TN', 'tier': 1, 'weight': 0.06},
    {'name': 'Kolkata', 'state': 'WB', 'tier': 1, 'weight': 0.05},
    {'name': 'Hyderabad', 'state': 'TG', 'tier': 1, 'weight': 0.06},
    {'name': 'Pune', 'state': 'MH', 'tier': 1, 'weight': 0.05},
    
    # Tier 2 (35% of transactions)
    {'name': 'Ahmedabad', 'state': 'GJ', 'tier': 2, 'weight': 0.04},
    {'name': 'Jaipur', 'state': 'RJ', 'tier': 2, 'weight': 0.03},
    {'name': 'Lucknow', 'state': 'UP', 'tier': 2, 'weight': 0.03},
    {'name': 'Chandigarh', 'state': 'CH', 'tier': 2, 'weight': 0.02},
    {'name': 'Indore', 'state': 'MP', 'tier': 2, 'weight': 0.02},
    {'name': 'Coimbatore', 'state': 'TN', 'tier': 2, 'weight': 0.02},
    {'name': 'Kochi', 'state': 'KL', 'tier': 2, 'weight': 0.02},
    {'name': 'Nagpur', 'state': 'MH', 'tier': 2, 'weight': 0.02},
    {'name': 'Vadodara', 'state': 'GJ', 'tier': 2, 'weight': 0.02},
    {'name': 'Visakhapatnam', 'state': 'AP', 'tier': 2, 'weight': 0.02},
    {'name': 'Surat', 'state': 'GJ', 'tier': 2, 'weight': 0.03},
    {'name': 'Bhopal', 'state': 'MP', 'tier': 2, 'weight': 0.02},
    
    # Tier 3 (25% of transactions)
    {'name': 'Patna', 'state': 'BR', 'tier': 3, 'weight': 0.02},
    {'name': 'Ranchi', 'state': 'JH', 'tier': 3, 'weight': 0.01},
    {'name': 'Bhubaneswar', 'state': 'OD', 'tier': 3, 'weight': 0.01},
    {'name': 'Dehradun', 'state': 'UK', 'tier': 3, 'weight': 0.01},
    {'name': 'Guwahati', 'state': 'AS', 'tier': 3, 'weight': 0.01},
    {'name': 'Thiruvananthapuram', 'state': 'KL', 'tier': 3, 'weight': 0.01},
    {'name': 'Varanasi', 'state': 'UP', 'tier': 3, 'weight': 0.01},
    {'name': 'Amritsar', 'state': 'PB', 'tier': 3, 'weight': 0.01},
    {'name': 'Mysore', 'state': 'KA', 'tier': 3, 'weight': 0.01},
    {'name': 'Jodhpur', 'state': 'RJ', 'tier': 3, 'weight': 0.01},
]

# ============ CHANNEL-CATEGORY MAPPINGS ============

@dataclass
class ChannelConfig:
    """Configuration for each payment channel"""
    name: str
    weight: float  # Overall frequency
    min_amount: int
    max_amount: int
    categories: List[str]  # Valid categories for this channel
    amount_multiplier: int = 1  # For ATM (multiples of 100)
    
CHANNELS = {
    'upi': ChannelConfig(
        name='UPI',
        weight=0.55,  # 55% of digital payments in India
        min_amount=1,
        max_amount=100000,
        categories=[
            'P2P Transfer', 'Grocery', 'Restaurant', 'Fuel Station', 
            'Bill Payment', 'Recharge', 'Food Delivery', 'Pharmacy',
            'Local Shop', 'Auto/Cab', 'Vegetables/Fruits'
        ]
    ),
    'pos': ChannelConfig(
        name='POS',
        weight=0.15,
        min_amount=50,
        max_amount=50000,
        categories=[
            'Retail Store', 'Supermarket', 'Fuel Station', 'Restaurant',
            'Electronics', 'Clothing', 'Jewellery', 'Department Store',
            'Medical Store', 'Hardware Store'
        ]
    ),
    'card_online': ChannelConfig(
        name='CARD_ONLINE',
        weight=0.12,
        min_amount=100,
        max_amount=200000,
        categories=[
            'E-commerce', 'Travel Booking', 'Subscription', 'Insurance',
            'Education', 'Electronics Online', 'Fashion Online',
            'Food Delivery', 'Grocery Online', 'Software/SaaS'
        ]
    ),
    'netbanking': ChannelConfig(
        name='NETBANKING',
        weight=0.08,
        min_amount=500,
        max_amount=1000000,
        categories=[
            'Loan EMI', 'Insurance Premium', 'Investment', 'Tax Payment',
            'Rent Payment', 'School Fees', 'Utility Bills', 'Property',
            'Large Transfer', 'Business Payment'
        ]
    ),
    'wallet': ChannelConfig(
        name='WALLET',
        weight=0.05,
        min_amount=1,
        max_amount=10000,
        categories=[
            'Recharge', 'Food Delivery', 'Auto/Cab', 'Bill Payment',
            'Local Shop', 'Movie Tickets', 'Gaming'
        ]
    ),
    'atm': ChannelConfig(
        name='ATM',
        weight=0.05,
        min_amount=100,
        max_amount=25000,
        categories=['Cash Withdrawal'],  # ATM = ONLY cash withdrawal
        amount_multiplier=100  # Must be multiple of ₹100
    )
}

# ============ REALISTIC AMOUNT DISTRIBUTIONS ============

def get_realistic_amount(channel: str, category: str) -> float:
    """Generate realistic amount based on channel and category"""
    config = CHANNELS.get(channel, CHANNELS['upi'])
    
    # Category-specific amount ranges
    category_amounts = {
        # UPI small transactions
        'P2P Transfer': (100, 25000),
        'Grocery': (200, 5000),
        'Restaurant': (150, 3000),
        'Fuel Station': (200, 5000),
        'Bill Payment': (100, 15000),
        'Recharge': (10, 2000),
        'Food Delivery': (100, 1500),
        'Pharmacy': (50, 3000),
        'Local Shop': (20, 2000),
        'Auto/Cab': (50, 1000),
        'Vegetables/Fruits': (50, 1000),
        
        # POS transactions
        'Retail Store': (200, 15000),
        'Supermarket': (500, 10000),
        'Electronics': (2000, 50000),
        'Clothing': (500, 15000),
        'Jewellery': (5000, 200000),
        'Department Store': (500, 20000),
        'Medical Store': (100, 5000),
        'Hardware Store': (200, 10000),
        
        # Online card
        'E-commerce': (300, 30000),
        'Travel Booking': (1000, 100000),
        'Subscription': (99, 2000),
        'Insurance': (500, 50000),
        'Education': (1000, 100000),
        'Electronics Online': (1000, 80000),
        'Fashion Online': (500, 15000),
        'Grocery Online': (300, 5000),
        'Software/SaaS': (500, 20000),
        
        # NetBanking high value
        'Loan EMI': (5000, 100000),
        'Insurance Premium': (2000, 50000),
        'Investment': (5000, 500000),
        'Tax Payment': (1000, 200000),
        'Rent Payment': (5000, 100000),
        'School Fees': (10000, 200000),
        'Utility Bills': (500, 10000),
        'Property': (50000, 1000000),
        'Large Transfer': (10000, 500000),
        'Business Payment': (5000, 500000),
        
        # Wallet small
        'Movie Tickets': (100, 1000),
        'Gaming': (10, 1000),
        
        # ATM
        'Cash Withdrawal': (500, 25000),
    }
    
    min_amt, max_amt = category_amounts.get(category, (config.min_amount, config.max_amount))
    
    # Clamp to channel limits
    min_amt = max(min_amt, config.min_amount)
    max_amt = min(max_amt, config.max_amount)
    
    # Generate amount with realistic distribution (log-normal for most)
    if channel == 'atm':
        # ATM: Multiples of ₹100, common values
        common_amounts = [500, 1000, 2000, 2500, 3000, 5000, 10000, 15000, 20000, 25000]
        weights = [0.15, 0.20, 0.20, 0.10, 0.10, 0.10, 0.08, 0.04, 0.02, 0.01]
        amount = random.choices(common_amounts, weights=weights)[0]
    else:
        # Log-normal distribution centered on median of range
        median = (min_amt + max_amt) / 3  # Skew towards lower amounts
        sigma = 0.8
        amount = np.random.lognormal(mean=np.log(median), sigma=sigma)
        amount = np.clip(amount, min_amt, max_amt)
        
        # Round to realistic values
        if amount < 100:
            amount = round(amount)
        elif amount < 1000:
            amount = round(amount / 10) * 10
        elif amount < 10000:
            amount = round(amount / 50) * 50
        else:
            amount = round(amount / 100) * 100
    
    return float(amount)


# ============ TRANSACTION GENERATOR ============

class TransactionGenerator:
    """Generates realistic Indian payment transactions"""
    
    def __init__(self, fraud_rate: float = 0.001):
        """
        Initialize generator.
        fraud_rate: Target fraud rate (default 0.1%)
        """
        self.fraud_rate = fraud_rate
        self.user_pool = self._create_user_pool(1000)
        self.device_pool = self._create_device_pool(500)
        self.txn_count = 0
    
    def _create_user_pool(self, n: int) -> List[Dict]:
        """Create pool of synthetic users"""
        users = []
        for i in range(n):
            city = random.choices(
                INDIAN_CITIES, 
                weights=[c['weight'] for c in INDIAN_CITIES]
            )[0]
            
            users.append({
                'user_id': f"USR{i:06d}",
                'home_city': city['name'],
                'home_state': city['state'],
                'tier': city['tier'],
                'preferred_channel': random.choices(
                    list(CHANNELS.keys()),
                    weights=[c.weight for c in CHANNELS.values()]
                )[0],
                'avg_monthly_txns': random.randint(10, 100),
                'created_days_ago': random.randint(30, 1000)
            })
        return users
    
    def _create_device_pool(self, n: int) -> List[Dict]:
        """Create pool of devices"""
        devices = []
        for i in range(n):
            devices.append({
                'device_id': f"DEV{i:08d}",
                'device_type': random.choice(['android', 'ios', 'web']),
                'age_days': random.randint(1, 500)
            })
        return devices
    
    def generate_transaction(self, force_fraud: bool = False) -> Dict[str, Any]:
        """Generate a single realistic transaction"""
        self.txn_count += 1
        is_fraud = force_fraud or (random.random() < self.fraud_rate)
        
        if is_fraud:
            return self._generate_fraud_transaction()
        return self._generate_normal_transaction()
    
    def _generate_normal_transaction(self) -> Dict[str, Any]:
        """Generate a normal (legitimate) transaction"""
        # Select user
        user = random.choice(self.user_pool)
        
        # Select channel (weighted)
        channel = random.choices(
            list(CHANNELS.keys()),
            weights=[c.weight for c in CHANNELS.values()]
        )[0]
        config = CHANNELS[channel]
        
        # Select category (must be valid for channel)
        category = random.choice(config.categories)
        
        # Generate amount
        amount = get_realistic_amount(channel, category)
        
        # Location (80% from home city)
        if random.random() < 0.8:
            city = next((c for c in INDIAN_CITIES if c['name'] == user['home_city']), INDIAN_CITIES[0])
        else:
            city = random.choices(
                INDIAN_CITIES,
                weights=[c['weight'] for c in INDIAN_CITIES]
            )[0]
        
        # Device
        device = random.choice(self.device_pool)
        is_new_device = random.random() < 0.05  # 5% new device
        
        # Time (realistic distribution)
        timestamp = self._get_realistic_timestamp()
        
        return {
            'transaction_id': str(uuid.uuid4()),
            'user_id': user['user_id'],
            'merchant_id': f"MER{random.randint(100000, 999999)}",
            'amount': amount,
            'channel': channel,
            'merchant_category': category,
            'transaction_type': 'debit',
            'city': city['name'],
            'state': city['state'],
            'country': 'IN',
            'timestamp': timestamp.isoformat(),
            'device_id': device['device_id'],
            'device_type': device['device_type'],
            'device_age_hours': device['age_days'] * 24,
            'is_new_device': is_new_device,
            'is_new_location': city['name'] != user['home_city'],
            'location_distance_km': 0 if city['name'] == user['home_city'] else random.uniform(50, 2000),
            'merchant_risk_score': random.uniform(0.05, 0.25),
            'is_fraud': False
        }
    
    def _generate_fraud_transaction(self) -> Dict[str, Any]:
        """Generate a fraudulent transaction"""
        fraud_type = random.choice([
            'account_takeover',
            'stolen_card',
            'high_velocity',
            'unusual_amount',
            'suspicious_category'
        ])
        
        user = random.choice(self.user_pool)
        
        if fraud_type == 'account_takeover':
            # New device + new location + unusual time
            channel = random.choice(['card_online', 'netbanking', 'upi'])
            config = CHANNELS[channel]
            category = random.choice(config.categories)
            amount = get_realistic_amount(channel, category) * random.uniform(2, 5)
            amount = min(amount, config.max_amount)
            
            # Far away city
            other_cities = [c for c in INDIAN_CITIES if c['name'] != user['home_city']]
            city = random.choice(other_cities)
            
            timestamp = self._get_fraud_timestamp()
            
            return {
                'transaction_id': str(uuid.uuid4()),
                'user_id': user['user_id'],
                'merchant_id': f"MER{random.randint(100000, 999999)}",
                'amount': amount,
                'channel': channel,
                'merchant_category': category,
                'transaction_type': 'debit',
                'city': city['name'],
                'state': city['state'],
                'country': 'IN',
                'timestamp': timestamp.isoformat(),
                'device_id': f"FRAUD_DEV_{uuid.uuid4().hex[:8]}",
                'device_type': random.choice(['android', 'web']),
                'device_age_hours': random.uniform(0, 24),  # Very new device
                'is_new_device': True,
                'is_new_location': True,
                'location_distance_km': random.uniform(500, 2500),
                'merchant_risk_score': random.uniform(0.5, 0.9),
                'is_fraud': True,
                'fraud_type': fraud_type
            }
        
        elif fraud_type == 'stolen_card':
            # Multiple high-value POS/online transactions
            channel = random.choice(['pos', 'card_online'])
            config = CHANNELS[channel]
            high_risk_cats = ['Electronics', 'Electronics Online', 'Jewellery', 'E-commerce']
            category = random.choice([c for c in config.categories if c in high_risk_cats] or config.categories)
            amount = random.uniform(15000, config.max_amount)
            
            city = random.choices(INDIAN_CITIES, weights=[c['weight'] for c in INDIAN_CITIES])[0]
            
            return {
                'transaction_id': str(uuid.uuid4()),
                'user_id': user['user_id'],
                'merchant_id': f"MER{random.randint(100000, 999999)}",
                'amount': amount,
                'channel': channel,
                'merchant_category': category,
                'transaction_type': 'debit',
                'city': city['name'],
                'state': city['state'],
                'country': 'IN',
                'timestamp': datetime.now().isoformat(),
                'device_id': f"FRAUD_DEV_{uuid.uuid4().hex[:8]}",
                'device_type': 'android',
                'device_age_hours': random.uniform(0, 48),
                'is_new_device': True,
                'is_new_location': random.random() < 0.7,
                'location_distance_km': random.uniform(100, 1000),
                'merchant_risk_score': random.uniform(0.6, 0.95),
                'is_fraud': True,
                'fraud_type': fraud_type
            }
        
        elif fraud_type == 'unusual_amount':
            # Amount way above user's normal pattern
            channel = random.choices(
                list(CHANNELS.keys()),
                weights=[c.weight for c in CHANNELS.values()]
            )[0]
            config = CHANNELS[channel]
            category = random.choice(config.categories)
            
            # Very high amount for channel
            amount = config.max_amount * random.uniform(0.7, 1.0)
            if channel == 'atm':
                amount = 25000  # Max ATM
            
            city = next((c for c in INDIAN_CITIES if c['name'] == user['home_city']), INDIAN_CITIES[0])
            
            return {
                'transaction_id': str(uuid.uuid4()),
                'user_id': user['user_id'],
                'merchant_id': f"MER{random.randint(100000, 999999)}",
                'amount': amount,
                'channel': channel,
                'merchant_category': category,
                'transaction_type': 'debit',
                'city': city['name'],
                'state': city['state'],
                'country': 'IN',
                'timestamp': datetime.now().isoformat(),
                'device_id': random.choice(self.device_pool)['device_id'],
                'device_type': random.choice(['android', 'ios']),
                'device_age_hours': random.uniform(100, 1000),
                'is_new_device': False,
                'is_new_location': False,
                'location_distance_km': 0,
                'merchant_risk_score': random.uniform(0.4, 0.7),
                'is_fraud': True,
                'fraud_type': fraud_type
            }
        
        else:  # high_velocity or suspicious_category
            channel = random.choice(['upi', 'card_online'])
            config = CHANNELS[channel]
            category = random.choice(config.categories)
            amount = get_realistic_amount(channel, category)
            
            city = random.choices(INDIAN_CITIES, weights=[c['weight'] for c in INDIAN_CITIES])[0]
            
            return {
                'transaction_id': str(uuid.uuid4()),
                'user_id': user['user_id'],
                'merchant_id': f"MER{random.randint(100000, 999999)}",
                'amount': amount,
                'channel': channel,
                'merchant_category': category,
                'transaction_type': 'debit',
                'city': city['name'],
                'state': city['state'],
                'country': 'IN',
                'timestamp': datetime.now().isoformat(),
                'device_id': random.choice(self.device_pool)['device_id'],
                'device_type': random.choice(['android', 'ios', 'web']),
                'device_age_hours': random.uniform(24, 500),
                'is_new_device': random.random() < 0.3,
                'is_new_location': random.random() < 0.5,
                'location_distance_km': random.uniform(0, 500),
                'merchant_risk_score': random.uniform(0.3, 0.6),
                'is_fraud': True,
                'fraud_type': fraud_type
            }
    
    def _get_realistic_timestamp(self) -> datetime:
        """Generate timestamp with realistic Indian time distribution"""
        now = datetime.now()
        
        # Hour distribution (IST): Peak at 10-12 AM and 6-9 PM
        hour_weights = [
            0.01, 0.005, 0.003, 0.002, 0.002, 0.005,  # 0-5 (night)
            0.01, 0.02, 0.04, 0.06, 0.08, 0.08,       # 6-11 (morning)
            0.07, 0.06, 0.05, 0.05, 0.06, 0.07,       # 12-17 (afternoon)
            0.08, 0.09, 0.08, 0.06, 0.04, 0.02        # 18-23 (evening)
        ]
        hour_weights = [w / sum(hour_weights) for w in hour_weights]
        hour = random.choices(range(24), weights=hour_weights)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        return now.replace(hour=hour, minute=minute, second=second)
    
    def _get_fraud_timestamp(self) -> datetime:
        """Generate timestamp for fraud (often odd hours)"""
        now = datetime.now()
        
        # Fraud more common at night
        if random.random() < 0.6:
            hour = random.choice([0, 1, 2, 3, 4, 23])
        else:
            hour = random.randint(0, 23)
        
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        return now.replace(hour=hour, minute=minute, second=second)
    
    def generate_batch(self, n: int, fraud_count: int = 0) -> List[Dict[str, Any]]:
        """Generate a batch of transactions"""
        transactions = []
        
        # Generate specified frauds first
        for _ in range(fraud_count):
            transactions.append(self._generate_fraud_transaction())
        
        # Generate remaining normal (with random fraud based on rate)
        for _ in range(n - fraud_count):
            transactions.append(self.generate_transaction())
        
        random.shuffle(transactions)
        return transactions


# Singleton
_generator_instance: Optional[TransactionGenerator] = None

def get_generator() -> TransactionGenerator:
    """Get or create transaction generator singleton"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = TransactionGenerator(fraud_rate=0.001)
    return _generator_instance

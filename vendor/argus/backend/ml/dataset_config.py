"""
ARGUS Dataset Configuration
===========================
All constants for Indian payment simulation calibrated to:
- NPCI 2024 transaction volume/value data
- RBI Master Directions on Fraud Risk Management (July 2024)
- FIU-IND STR/CTR reporting thresholds (PMLA 2002)
- NPCI UPI limits effective Sept 15, 2025
"""

# ============ INDIAN CITIES (30 cities, 3 tiers) ============

INDIAN_CITIES = [
    # Tier 1 — 59% weight
    {'name': 'Mumbai', 'state': 'MH', 'tier': 1, 'weight': 0.15, 'lat': 19.07, 'lon': 72.87},
    {'name': 'Delhi', 'state': 'DL', 'tier': 1, 'weight': 0.12, 'lat': 28.61, 'lon': 77.20},
    {'name': 'Bangalore', 'state': 'KA', 'tier': 1, 'weight': 0.10, 'lat': 12.97, 'lon': 77.59},
    {'name': 'Chennai', 'state': 'TN', 'tier': 1, 'weight': 0.06, 'lat': 13.08, 'lon': 80.27},
    {'name': 'Kolkata', 'state': 'WB', 'tier': 1, 'weight': 0.05, 'lat': 22.57, 'lon': 88.36},
    {'name': 'Hyderabad', 'state': 'TG', 'tier': 1, 'weight': 0.06, 'lat': 17.38, 'lon': 78.49},
    {'name': 'Pune', 'state': 'MH', 'tier': 1, 'weight': 0.05, 'lat': 18.52, 'lon': 73.85},
    # Tier 2 — 27% weight
    {'name': 'Ahmedabad', 'state': 'GJ', 'tier': 2, 'weight': 0.04, 'lat': 23.02, 'lon': 72.57},
    {'name': 'Jaipur', 'state': 'RJ', 'tier': 2, 'weight': 0.03, 'lat': 26.91, 'lon': 75.78},
    {'name': 'Lucknow', 'state': 'UP', 'tier': 2, 'weight': 0.03, 'lat': 26.84, 'lon': 80.94},
    {'name': 'Chandigarh', 'state': 'CH', 'tier': 2, 'weight': 0.02, 'lat': 30.73, 'lon': 76.77},
    {'name': 'Indore', 'state': 'MP', 'tier': 2, 'weight': 0.02, 'lat': 22.71, 'lon': 75.85},
    {'name': 'Coimbatore', 'state': 'TN', 'tier': 2, 'weight': 0.02, 'lat': 11.01, 'lon': 76.95},
    {'name': 'Kochi', 'state': 'KL', 'tier': 2, 'weight': 0.02, 'lat': 9.93, 'lon': 76.26},
    {'name': 'Nagpur', 'state': 'MH', 'tier': 2, 'weight': 0.02, 'lat': 21.14, 'lon': 79.08},
    {'name': 'Surat', 'state': 'GJ', 'tier': 2, 'weight': 0.03, 'lat': 21.17, 'lon': 72.83},
    {'name': 'Bhopal', 'state': 'MP', 'tier': 2, 'weight': 0.02, 'lat': 23.25, 'lon': 77.41},
    {'name': 'Vadodara', 'state': 'GJ', 'tier': 2, 'weight': 0.02, 'lat': 22.30, 'lon': 73.18},
    # Tier 3 — 14% weight
    {'name': 'Patna', 'state': 'BR', 'tier': 3, 'weight': 0.02, 'lat': 25.61, 'lon': 85.14},
    {'name': 'Ranchi', 'state': 'JH', 'tier': 3, 'weight': 0.01, 'lat': 23.34, 'lon': 85.30},
    {'name': 'Bhubaneswar', 'state': 'OD', 'tier': 3, 'weight': 0.01, 'lat': 20.29, 'lon': 85.82},
    {'name': 'Dehradun', 'state': 'UK', 'tier': 3, 'weight': 0.01, 'lat': 30.31, 'lon': 78.03},
    {'name': 'Guwahati', 'state': 'AS', 'tier': 3, 'weight': 0.01, 'lat': 26.14, 'lon': 91.73},
    {'name': 'Thiruvananthapuram', 'state': 'KL', 'tier': 3, 'weight': 0.01, 'lat': 8.52, 'lon': 76.93},
    {'name': 'Varanasi', 'state': 'UP', 'tier': 3, 'weight': 0.01, 'lat': 25.31, 'lon': 83.01},
    {'name': 'Amritsar', 'state': 'PB', 'tier': 3, 'weight': 0.01, 'lat': 31.63, 'lon': 74.87},
    {'name': 'Mysore', 'state': 'KA', 'tier': 3, 'weight': 0.01, 'lat': 12.29, 'lon': 76.63},
    {'name': 'Jodhpur', 'state': 'RJ', 'tier': 3, 'weight': 0.01, 'lat': 26.28, 'lon': 73.02},
    {'name': 'Visakhapatnam', 'state': 'AP', 'tier': 3, 'weight': 0.01, 'lat': 17.68, 'lon': 83.21},
    {'name': 'Mangalore', 'state': 'KA', 'tier': 3, 'weight': 0.01, 'lat': 12.91, 'lon': 74.85},
]

CITY_WEIGHTS = [c['weight'] for c in INDIAN_CITIES]

# ============ CHANNEL CONFIGS (NPCI 2024 calibrated) ============

CHANNELS = {
    'upi': {
        'weight': 0.55, 'min': 1, 'max': 100000,
        'categories': [
            'P2P Transfer', 'Grocery', 'Restaurant', 'Fuel Station',
            'Bill Payment', 'Recharge', 'Food Delivery', 'Pharmacy',
            'Local Shop', 'Auto/Cab', 'Vegetables/Fruits', 'Tea/Snacks',
            'Stationery', 'Laundry', 'Parking', 'Newspaper',
        ],
    },
    'pos': {
        'weight': 0.15, 'min': 20, 'max': 500000,
        'categories': [
            'Retail Store', 'Supermarket', 'Fuel Station', 'Restaurant',
            'Electronics', 'Clothing', 'Jewellery', 'Department Store',
            'Medical Store', 'Hardware Store', 'Salon/Barber',
        ],
    },
    'card_online': {
        'weight': 0.12, 'min': 49, 'max': 200000,
        'categories': [
            'E-commerce', 'Travel Booking', 'Subscription', 'Insurance',
            'Education', 'Electronics Online', 'Fashion Online',
            'Food Delivery', 'Grocery Online', 'Software/SaaS',
        ],
    },
    'netbanking': {
        'weight': 0.08, 'min': 500, 'max': 1000000,
        'categories': [
            'Loan EMI', 'Insurance Premium', 'Investment', 'Tax Payment',
            'Rent Payment', 'School Fees', 'Utility Bills', 'Property',
            'Large Transfer', 'Business Payment',
        ],
    },
    'wallet': {
        'weight': 0.05, 'min': 1, 'max': 10000,
        'categories': [
            'Recharge', 'Food Delivery', 'Auto/Cab', 'Bill Payment',
            'Local Shop', 'Movie Tickets', 'Gaming', 'Tea/Snacks',
        ],
    },
    'atm': {
        'weight': 0.05, 'min': 100, 'max': 25000,
        'categories': ['Cash Withdrawal'],
    },
}

CHANNEL_WEIGHTS = [v['weight'] for v in CHANNELS.values()]
CHANNEL_NAMES = list(CHANNELS.keys())

# ============ CATEGORY-SPECIFIC AMOUNT RANGES ============
# Calibrated to real Indian spending: ₹5 eraser to ₹10L property

CATEGORY_AMOUNTS = {
    # Micro (₹1-100)
    'Tea/Snacks': (5, 150),
    'Stationery': (5, 200),
    'Parking': (10, 100),
    'Newspaper': (5, 50),
    # Small (₹10-1000)
    'Auto/Cab': (20, 800),
    'Vegetables/Fruits': (30, 800),
    'Laundry': (50, 500),
    'Salon/Barber': (100, 800),
    'Recharge': (10, 2999),
    'Local Shop': (10, 3000),
    'Gaming': (10, 1000),
    # Medium
    'Grocery': (100, 8000),
    'Restaurant': (80, 5000),
    'Fuel Station': (100, 6000),
    'Food Delivery': (80, 2500),
    'Pharmacy': (30, 5000),
    'Medical Store': (50, 8000),
    'Bill Payment': (50, 15000),
    'Movie Tickets': (100, 2000),
    'Grocery Online': (200, 6000),
    'Utility Bills': (200, 12000),
    'P2P Transfer': (10, 50000),
    'Subscription': (49, 3000),
    # Large
    'Retail Store': (200, 25000),
    'Supermarket': (300, 15000),
    'Clothing': (300, 20000),
    'Department Store': (500, 30000),
    'Hardware Store': (100, 15000),
    'Fashion Online': (300, 20000),
    'Software/SaaS': (200, 25000),
    'E-commerce': (100, 50000),
    'Loan EMI': (2000, 100000),
    'Insurance Premium': (500, 60000),
    'Rent Payment': (3000, 120000),
    'School Fees': (5000, 200000),
    'Tax Payment': (1000, 300000),
    # Very Large
    'Electronics': (1000, 150000),
    'Electronics Online': (500, 120000),
    'Jewellery': (2000, 500000),
    'Travel Booking': (500, 150000),
    'Education': (1000, 200000),
    'Investment': (1000, 500000),
    'Large Transfer': (5000, 500000),
    'Business Payment': (5000, 500000),
    'Property': (50000, 1000000),
    'Insurance': (500, 60000),
    # ATM
    'Cash Withdrawal': (100, 25000),
}

# ============ CHANNEL RISK SCORES ============

CHANNEL_RISK = {
    'upi': 0.12, 'pos': 0.18, 'card_online': 0.32,
    'netbanking': 0.22, 'wallet': 0.08, 'atm': 0.28,
}

CATEGORY_RISK = {
    'P2P Transfer': 0.25, 'Cash Withdrawal': 0.30, 'Electronics': 0.35,
    'Electronics Online': 0.33, 'Jewellery': 0.45, 'Large Transfer': 0.30,
    'Property': 0.20, 'Investment': 0.18, 'Business Payment': 0.22,
    'E-commerce': 0.15, 'Travel Booking': 0.12, 'Grocery': 0.03,
    'Grocery Online': 0.04, 'Vegetables/Fruits': 0.02, 'Tea/Snacks': 0.01,
    'Stationery': 0.01, 'Parking': 0.01, 'Newspaper': 0.01,
    'Restaurant': 0.05, 'Fuel Station': 0.06, 'Food Delivery': 0.04,
    'Recharge': 0.03, 'Pharmacy': 0.03, 'Medical Store': 0.03,
    'Local Shop': 0.04, 'Auto/Cab': 0.03, 'Bill Payment': 0.03,
    'Utility Bills': 0.03, 'Subscription': 0.05, 'Insurance': 0.04,
    'Insurance Premium': 0.04, 'Education': 0.03, 'School Fees': 0.03,
    'Loan EMI': 0.04, 'Rent Payment': 0.05, 'Tax Payment': 0.02,
    'Retail Store': 0.08, 'Supermarket': 0.05, 'Clothing': 0.08,
    'Fashion Online': 0.07, 'Department Store': 0.07, 'Hardware Store': 0.05,
    'Salon/Barber': 0.02, 'Software/SaaS': 0.05, 'Movie Tickets': 0.03,
    'Gaming': 0.06, 'Laundry': 0.02,
}

# ============ VALID CHANNEL-CATEGORY PAIRS ============
# ATM can ONLY be Cash Withdrawal. Wallet can't do Jewellery. etc.

def is_valid_channel_category(channel: str, category: str) -> bool:
    """Check if a category is valid for a given channel per RBI/NPCI rules"""
    return category in CHANNELS.get(channel, {}).get('categories', [])

# ============ RBI/NPCI REGULATORY LIMITS ============

REGULATORY_LIMITS = {
    'upi_single': 100000,        # ₹1L per UPI txn (general)
    'upi_daily': 100000,         # ₹1L daily UPI (general P2P)
    'upi_capital_markets': 500000,  # ₹5L for IPO/MF via UPI
    'upi_insurance': 500000,     # ₹5L for insurance via UPI
    'upi_new_user_24h': 5000,    # ₹5K for first 24hrs (NPCI mandate)
    'atm_single': 25000,         # ₹25K per ATM withdrawal
    'atm_daily': 25000,          # ₹25K daily ATM
    'wallet_single': 10000,      # ₹10K wallet (min KYC PPI)
    'wallet_full_kyc': 200000,   # ₹2L wallet (full KYC PPI)
    'str_threshold': 1000000,    # ₹10L — FIU-IND STR reporting
    'ctr_monthly': 1000000,      # ₹10L monthly cash — CTR trigger
    'cooling_period_hours': 1,   # 1-hour proposed cooling (RBI April 2026)
    'senior_citizen_limit': 50000,  # ₹50K enhanced auth for 70+ (proposed)
}

# ============ HOUR DISTRIBUTION (IST) ============

HOUR_WEIGHTS_NORMAL = [
    0.008, 0.004, 0.002, 0.002, 0.002, 0.005,  # 0-5 (dead night)
    0.010, 0.025, 0.045, 0.065, 0.080, 0.080,   # 6-11 (morning rush)
    0.070, 0.060, 0.050, 0.050, 0.060, 0.070,   # 12-17 (afternoon)
    0.080, 0.090, 0.080, 0.060, 0.035, 0.017,   # 18-23 (evening peak)
]
# Normalize
_s = sum(HOUR_WEIGHTS_NORMAL)
HOUR_WEIGHTS_NORMAL = [w / _s for w in HOUR_WEIGHTS_NORMAL]

HOUR_WEIGHTS_FRAUD = [
    0.08, 0.10, 0.12, 0.10, 0.06, 0.04,  # 0-5 (fraud peaks here)
    0.03, 0.03, 0.03, 0.04, 0.04, 0.04,  # 6-11
    0.03, 0.03, 0.03, 0.03, 0.03, 0.03,  # 12-17
    0.03, 0.03, 0.03, 0.03, 0.03, 0.04,  # 18-23
]
_s2 = sum(HOUR_WEIGHTS_FRAUD)
HOUR_WEIGHTS_FRAUD = [w / _s2 for w in HOUR_WEIGHTS_FRAUD]

# ATM common withdrawal amounts (multiples of ₹100)
ATM_COMMON_AMOUNTS = [500, 1000, 2000, 2500, 3000, 5000, 10000, 15000, 20000, 25000]
ATM_AMOUNT_WEIGHTS = [0.15, 0.22, 0.20, 0.08, 0.10, 0.12, 0.07, 0.03, 0.02, 0.01]

# Structuring amounts (just below STR threshold)
STRUCTURING_AMOUNTS = [
    990000, 950000, 900000, 980000, 970000,  # Just below ₹10L
    490000, 480000, 450000,  # Below ₹5L
    99000, 95000,  # Below ₹1L
]

# Round amounts common in mule/layering
MULE_ROUND_AMOUNTS = [
    10000, 25000, 50000, 100000, 200000, 500000,
]

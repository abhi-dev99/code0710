"""
UPI-Specific Fraud Detection Patterns
India-specific fraud scenarios based on real-world cases
"""

import re
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

class UPIFraudDetector:
    """
    Detects India-specific fraud patterns:
    1. Digital Arrest Scams
    2. SIM Swap Attacks
    3. Mule Account Chains
    4. Merchant Impersonation
    5. QR Code Fraud
    6. UPI ID Phishing
    7. Fake Payment Screenshot Scams
    """
    
    def __init__(self):
        # Government agency impersonation patterns
        self.govt_keywords = [
            'police', 'cbi', 'ed', 'income tax', 'customs',
            'narcotics', 'cyber cell', 'law enforcement', 'arrest warrant',
            'investigation', 'supreme court', 'rbi', 'sebi'
        ]
        
        # Known mule account patterns (rapid fund movement)
        self.mule_patterns = {
            'rapid_in_out': 5,  # 5+ transactions in/out within 1 hour
            'round_numbers': [1000, 5000, 10000, 25000, 50000, 100000],
            'cascade_count': 3  # Money flows through 3+ accounts
        }
        
        # UPI ID patterns indicating fraud
        self.suspicious_upi_patterns = [
            r'^\d{10}@',  # Only phone number as UPI ID (common in scams)
            r'(test|temp|dummy|fake).*@',
            r'^[a-z]{2,4}\d{6,}@',  # Very short name + long numbers
            r'.*\d{8,}@'  # 8+ consecutive digits
        ]
        
    def detect_digital_arrest_scam(self, txn: Dict) -> Tuple[bool, str, float]:
        """
        Digital Arrest Scam Detection:
        - Victim receives call from fake police/CBI/ED
        - Asked to transfer money for "investigation" or to "save account"
        - Multiple transfers to different accounts in short time
        - Transfers to accounts with govt-sounding names
        """
        risk_score = 0.0
        reasons = []
        
        merchant = txn.get('merchant_name', '').lower()
        notes = txn.get('notes', '').lower()
        amount = txn.get('amount', 0)
        
        # Check for govt agency keywords in merchant/notes
        for keyword in self.govt_keywords:
            if keyword in merchant or keyword in notes:
                risk_score += 0.4
                reasons.append(f"Govt agency keyword '{keyword}' detected")
                break
        
        # High-value transfers to individual accounts (not businesses)
        if amount > 50000 and txn.get('merchant_category') == 'individual':
            risk_score += 0.3
            reasons.append("Large transfer to individual account")
        
        # Multiple transfers in short duration
        user_id = txn.get('user_id')
        recent_count = txn.get('user_txn_count_1h', 0)
        if recent_count >= 3 and amount > 10000:
            risk_score += 0.35
            reasons.append(f"{recent_count} transfers in last hour")
        
        is_fraud = risk_score >= 0.7
        reason_str = " | ".join(reasons) if reasons else ""
        
        return is_fraud, f"DIGITAL_ARREST_SCAM: {reason_str}", min(risk_score, 1.0)
    
    def detect_sim_swap_attack(self, txn: Dict) -> Tuple[bool, str, float]:
        """
        SIM Swap Attack Detection:
        - Sudden device change + immediate high-value transfers
        - Location change (different state)
        - Transaction patterns break from history
        """
        risk_score = 0.0
        reasons = []
        
        device_id = txn.get('device_id', '')
        prev_device = txn.get('user_prev_device_id', '')
        location = txn.get('location', '')
        prev_location = txn.get('user_prev_location', '')
        amount = txn.get('amount', 0)
        account_age_days = txn.get('account_age_days', 999)
        
        # New device detected
        if device_id and prev_device and device_id != prev_device:
            risk_score += 0.35
            reasons.append("New device detected")
            
            # High-value transaction on new device
            if amount > 25000:
                risk_score += 0.3
                reasons.append("Large amount on new device")
        
        # Location change
        if location and prev_location and location != prev_location:
            # Different state/city
            if not any(word in prev_location.lower() for word in location.lower().split()):
                risk_score += 0.25
                reasons.append(f"Location changed: {prev_location} → {location}")
        
        # Transaction outside normal hours (2 AM - 6 AM)
        hour = datetime.now().hour
        if 2 <= hour <= 6 and amount > 10000:
            risk_score += 0.15
            reasons.append("Unusual hour transaction")
        
        is_fraud = risk_score >= 0.65
        reason_str = " | ".join(reasons) if reasons else ""
        
        return is_fraud, f"SIM_SWAP_ATTACK: {reason_str}", min(risk_score, 1.0)
    
    def detect_mule_account(self, txn: Dict, user_history: List[Dict]) -> Tuple[bool, str, float]:
        """
        Mule Account Detection:
        - New account (< 30 days)
        - Receives money from multiple sources
        - Immediately transfers out
        - Round number transactions
        - No genuine economic activity
        """
        risk_score = 0.0
        reasons = []
        
        account_age_days = txn.get('account_age_days', 999)
        amount = txn.get('amount', 0)
        txn_type = txn.get('type', 'debit')
        
        # New account activity
        if account_age_days < 30:
            risk_score += 0.2
            reasons.append(f"New account ({account_age_days} days old)")
        
        # Round number transactions (common in mule accounts)
        if amount in self.mule_patterns['round_numbers']:
            risk_score += 0.15
            reasons.append(f"Round amount: ₹{amount}")
        
        # Analyze transaction pattern
        if len(user_history) >= 5:
            credits = [t for t in user_history if t.get('type') == 'credit']
            debits = [t for t in user_history if t.get('type') == 'debit']
            
            # Money-in-money-out pattern
            if len(credits) >= 3 and len(debits) >= 3:
                avg_credit = sum(t.get('amount', 0) for t in credits) / len(credits)
                avg_debit = sum(t.get('amount', 0) for t in debits) / len(debits)
                
                # Similar amounts in/out (with safe division)
                if avg_credit > 0 and 0.8 <= avg_debit / avg_credit <= 1.2:
                    risk_score += 0.35
                    reasons.append("Money-in-money-out pattern detected")
            
            # Multiple unique senders/receivers
            unique_senders = len(set(t.get('sender_upi') for t in credits if t.get('sender_upi')))
            unique_receivers = len(set(t.get('receiver_upi') for t in debits if t.get('receiver_upi')))
            
            if unique_senders >= 5 and unique_receivers >= 3:
                risk_score += 0.3
                reasons.append(f"Multiple senders ({unique_senders}) and receivers ({unique_receivers})")
        
        is_fraud = risk_score >= 0.6
        reason_str = " | ".join(reasons) if reasons else ""
        
        return is_fraud, f"MULE_ACCOUNT: {reason_str}", min(risk_score, 1.0)
    
    def detect_qr_code_fraud(self, txn: Dict) -> Tuple[bool, str, float]:
        """
        QR Code Fraud Detection:
        - Victim scans malicious QR code
        - Money request instead of payment
        - Merchant name mismatch
        """
        risk_score = 0.0
        reasons = []
        
        payment_method = txn.get('payment_method', '')
        merchant_name = txn.get('merchant_name', '').lower()
        merchant_category = txn.get('merchant_category', '')
        amount = txn.get('amount', 0)
        
        # QR-based transaction
        if 'qr' in payment_method.lower():
            # High amount via QR to unknown merchant
            if amount > 5000 and merchant_category == 'individual':
                risk_score += 0.3
                reasons.append("High-value QR payment to individual")
            
            # Suspicious merchant names
            suspicious_terms = ['update', 'kyc', 'verify', 'reward', 'cashback', 'prize']
            if any(term in merchant_name for term in suspicious_terms):
                risk_score += 0.4
                reasons.append(f"Suspicious merchant name: {merchant_name}")
        
        is_fraud = risk_score >= 0.5
        reason_str = " | ".join(reasons) if reasons else ""
        
        return is_fraud, f"QR_CODE_FRAUD: {reason_str}", min(risk_score, 1.0)
    
    def detect_upi_id_phishing(self, txn: Dict) -> Tuple[bool, str, float]:
        """
        UPI ID Phishing Detection:
        - Suspicious UPI ID patterns
        - Mismatched merchant names
        """
        risk_score = 0.0
        reasons = []
        
        receiver_upi = txn.get('receiver_upi', '')
        merchant_name = txn.get('merchant_name', '')
        
        # Check UPI ID against suspicious patterns
        for pattern in self.suspicious_upi_patterns:
            if re.match(pattern, receiver_upi):
                risk_score += 0.35
                reasons.append(f"Suspicious UPI ID pattern: {receiver_upi}")
                break
        
        # UPI ID and merchant name mismatch
        if receiver_upi and merchant_name:
            upi_prefix = receiver_upi.split('@')[0].lower()
            merchant_clean = re.sub(r'[^a-z0-9]', '', merchant_name.lower())
            
            # No common substring
            if not any(word in merchant_clean for word in upi_prefix.split('.') if len(word) > 3):
                risk_score += 0.25
                reasons.append("UPI ID doesn't match merchant name")
        
        is_fraud = risk_score >= 0.5
        reason_str = " | ".join(reasons) if reasons else ""
        
        return is_fraud, f"UPI_ID_PHISHING: {reason_str}", min(risk_score, 1.0)
    
    def analyze_transaction(self, txn: Dict, user_history: List[Dict] = None) -> Dict:
        """
        Run all UPI fraud detection checks
        """
        user_history = user_history or []
        results = []
        max_risk = 0.0
        fraud_types = []
        
        # Run all detectors
        detectors = [
            self.detect_digital_arrest_scam(txn),
            self.detect_sim_swap_attack(txn),
            self.detect_mule_account(txn, user_history),
            self.detect_qr_code_fraud(txn),
            self.detect_upi_id_phishing(txn)
        ]
        
        for is_fraud, reason, risk in detectors:
            if is_fraud:
                fraud_type = reason.split(':')[0]
                fraud_types.append(fraud_type)
                results.append(reason)
                max_risk = max(max_risk, risk)
        
        return {
            'is_upi_fraud': len(fraud_types) > 0,
            'fraud_types': fraud_types,
            'upi_risk_score': max_risk,
            'reasons': results,
            'rbi_category': self._get_rbi_category(fraud_types)
        }
    
    def _get_rbi_category(self, fraud_types: List[str]) -> str:
        """
        Categorize per RBI fraud classification
        """
        if 'DIGITAL_ARREST_SCAM' in fraud_types:
            return "Social Engineering/Impersonation Fraud"
        elif 'SIM_SWAP_ATTACK' in fraud_types:
            return "Account Takeover Fraud"
        elif 'MULE_ACCOUNT' in fraud_types:
            return "Money Laundering/Mule Account"
        elif 'QR_CODE_FRAUD' in fraud_types or 'UPI_ID_PHISHING' in fraud_types:
            return "Digital Payment Fraud"
        return "Other"

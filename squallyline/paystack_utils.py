import requests
from django.conf import settings
import json
import hmac
import hashlib
import logging
from decimal import Decimal, InvalidOperation 

logger = logging.getLogger(__name__)


class PaystackAPI:
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.base_url = "https://api.paystack.co"
    
    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
    
    def initialize_transaction(self, email, amount, reference=None, callback_url=None):
        """Initialize a payment transaction"""
        url = f"{self.base_url}/transaction/initialize"
        
        data = {
            "email": email,
            "amount": int(amount * 100),  
            "currency": "GHS",
            "callback_url": callback_url or settings.PAYSTACK_CALLBACK_URL
        }
        
        if reference:
            data["reference"] = reference
            
        response = requests.post(url, headers=self._get_headers(), json=data)
        return response.json()
    

    def verify_webhook(self, payload, signature):
        """
        Verify Paystack webhook signature
        """
        if not signature or not payload:
            return False
            
        try:
            computed_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            return hmac.compare_digest(computed_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook: {e}")
            return False
    
    def verify_transaction(self, reference):
        """
        Verifies a transaction using the Paystack API
        """
        url = f"{self.base_url}/transaction/verify/{reference}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            return data  # Return full response
            
        except requests.exceptions.RequestException as err:
            logger.error(f"Error verifying transaction {reference}: {err}")
            return {'status': False, 'message': str(err)}
        except json.JSONDecodeError as err:
            logger.error(f"JSON error for transaction {reference}: {err}")
            return {'status': False, 'message': 'Invalid response from Paystack'}

    
    def create_transfer_recipient(self, recipient_type, name, **kwargs):
        url = f"{self.base_url}/transferrecipient"
        
        data = {
            "type": recipient_type,
            "name": name,
            "currency": kwargs.get('currency', 'GHS')
        }
        
        # Add type-specific details
        if recipient_type == "nuban":
            data["account_number"] = kwargs['account_number']
            data["bank_code"] = kwargs['bank_code']
        elif recipient_type == "mobile_money":
            data["details"] = {
                "phone": kwargs['phone'],
                "provider": kwargs['provider']
            }
        else:
            raise ValueError(f"Unsupported recipient type: {recipient_type}")
            
        response = requests.post(url, headers=self._get_headers(), json=data)
        return response.json()
      
    def initiate_transfer(self, amount, recipient_code, reason):
        """Initiate transfer to recipient"""
        url = f"{self.base_url}/transfer"
        data = {
            "source": "balance",
            "amount": int(amount * 100),
            "recipient": recipient_code,
            "reason": reason
        }
        response = requests.post(url, headers=self._get_headers(), json=data)
        return response.json()
    
    def list_banks(self, country="ghana", currency="GHS"):
        """Get list of supported banks"""
        url = f"{self.base_url}/bank"
        params = {
            "country": country,
            "currency": currency
        }
        response = requests.get(url, headers=self._get_headers(), params=params)
        return response.json()
    
    def check_wallet_balance(self, user, amount):
        """Check if user has sufficient wallet balance"""
        if not hasattr(user, 'wallet'):
            return False
        return user.wallet.balance >= Decimal(str(amount))


    def deduct_wallet_balance(self, user, amount):
        """Deduct amount from user's wallet"""
        wallet = user.wallet
        if wallet.balance < Decimal(str(amount)):
            raise ValueError("Insufficient balance")
        wallet.balance -= Decimal(str(amount))
        wallet.save()
        return wallet.balance


    def refund_wallet_balance(self, user, amount):
        """Refund amount back to user's wallet"""
        wallet = user.wallet
        wallet.balance += Decimal(str(amount))
        wallet.save()
        return wallet.balance


    def generate_transfer_reference(self, user_id):
        """Generate unique reference for transfer"""
        import time
        import random
        import string
        timestamp = int(time.time() * 1000)
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"WDL_{user_id}_{timestamp}_{random_str}"




    def create_paystack_recipient(self, user, data):
        """Create transfer recipient on Paystack"""
        provider_type = data.get('provider_type')
        account_holder_name = data.get('account_holder_name')
        
        if provider_type == 'bank':
            payload = {
                "type": "nuban",
                "name": account_holder_name,
                "account_number": data['account_number'],
                "bank_code": data['bank_code'],
                "currency": "GHS"
            }
        else:
            # Mobile money - correct structure per Paystack docs
            # Map network to Paystack bank_code values
            bank_code_mapping = {
                'mtn': 'MTN',
                'telecel': 'VOD',
                'airteltigo': 'ATL'
            }
            bank_code = bank_code_mapping.get(data.get('mobile_money_network'), 'MTN')
            
            payload = {
                "type": "mobile_money",
                "name": account_holder_name,
                "account_number": data['mobile_money_number'],
                "bank_code": bank_code,
                "currency": "GHS"
            }
        
        url = f"{self.base_url}/transferrecipient"
        response = requests.post(url, json=payload, headers=self._get_headers())
        result = response.json()
        
        print(f"Paystack request: {payload}")
        print(f"Paystack response: {result}")
        
        if not result.get('status'):
            error_msg = result.get('message', 'Unknown error')
            raise Exception(f"Paystack error: {error_msg}")
        
        return result['data']['recipient_code']




    def initiate_paystack_transfer(self, recipient_code, amount, reference, reason=None):
        """Initiate transfer to recipient"""
        amount_in_pesewas = int(Decimal(str(amount)) * 100)
        
        payload = {
            "source": "balance",
            "amount": amount_in_pesewas,
            "recipient": recipient_code,
            "reference": reference,
            "reason": reason or "Wallet withdrawal"
        }
        
        url = f"{self.base_url}/transfer"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        result = response.json()
        
        if not result.get('status'):
            raise Exception(f"Transfer failed: {result.get('message', 'Unknown error')}")
        
        return result['data']
    


# Helper functions
def get_paystack_client():
    return PaystackAPI()

def is_payment_successful(verify_response):
    """Check if payment was successful with proper error handling"""
    try:
        return (verify_response.get('status') is True and 
                verify_response.get('data', {}).get('status') == 'success')
    except (KeyError, AttributeError, TypeError):
        return False
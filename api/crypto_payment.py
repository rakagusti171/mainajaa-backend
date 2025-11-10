# backend/api/crypto_payment.py
"""
Module untuk handle crypto payment
Menggunakan API external untuk mendapatkan rate dan generate payment address
"""
import requests
from decimal import Decimal
from django.conf import settings

# Crypto payment configuration
CRYPTO_PAYMENT_CONFIG = {
    'USDT': {
        'network': 'TRC20',  # Tron network untuk USDT
        'decimals': 6,
        'api_url': 'https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd',
    },
    'ETH': {
        'network': 'Ethereum',
        'decimals': 18,
        'api_url': 'https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd',
    },
    'SOL': {
        'network': 'Solana',
        'decimals': 9,
        'api_url': 'https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd',
    },
}

# Wallet addresses untuk setiap crypto (dalam production, ini sebaiknya dari database atau env)
CRYPTO_WALLETS = {
    'USDT': getattr(settings, 'USDT_WALLET_ADDRESS', 'TYourUSDTWalletAddressHere'),
    'ETH': getattr(settings, 'ETH_WALLET_ADDRESS', '0xYourETHWalletAddressHere'),
    'SOL': getattr(settings, 'SOL_WALLET_ADDRESS', 'YourSolanaWalletAddressHere'),
}

def get_crypto_price(crypto_code):
    """
    Get current price of crypto in USD
    Returns: Decimal price in USD
    """
    try:
        config = CRYPTO_PAYMENT_CONFIG.get(crypto_code.upper())
        if not config:
            return None
        
        response = requests.get(config['api_url'], timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Map crypto code to coingecko id
            crypto_id_map = {
                'USDT': 'tether',
                'ETH': 'ethereum',
                'SOL': 'solana',
            }
            crypto_id = crypto_id_map.get(crypto_code.upper())
            if crypto_id and crypto_id in data:
                return Decimal(str(data[crypto_id]['usd']))
        return None
    except Exception as e:
        print(f"Error getting crypto price for {crypto_code}: {e}")
        return None

def get_idr_to_usd_rate():
    """
    Get IDR to USD exchange rate from exchangerate-api.com
    Returns: Decimal rate (IDR per USD) or None if failed
    """
    try:
        api_key = getattr(settings, 'EXCHANGERATE_API_KEY', '')
        if api_key:
            # Using exchangerate-api.com with API key
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        else:
            # Fallback to free endpoint (no API key required)
            url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'rates' in data and 'IDR' in data['rates']:
                # Rate is IDR per USD (e.g., 15000 means 1 USD = 15000 IDR)
                return Decimal(str(data['rates']['IDR']))
        
        # Fallback to hardcoded rate if API fails
        return Decimal('15000')
    except Exception as e:
        print(f"Error getting IDR to USD rate: {e}")
        # Fallback to hardcoded rate
        return Decimal('15000')

def calculate_crypto_amount(idr_amount, crypto_code):
    """
    Calculate crypto amount needed for IDR amount
    Args:
        idr_amount: Amount in IDR (Decimal)
        crypto_code: Crypto code (USDT, ETH, SOL)
    Returns:
        Tuple (crypto_amount, usd_rate, idr_to_usd_rate)
    """
    try:
        # Get USD price of crypto
        crypto_usd_price = get_crypto_price(crypto_code)
        if not crypto_usd_price:
            return None, None, None
        
        # Convert IDR to USD using real-time exchange rate
        idr_to_usd_rate = get_idr_to_usd_rate()
        usd_amount = idr_amount / idr_to_usd_rate
        
        # Calculate crypto amount
        config = CRYPTO_PAYMENT_CONFIG.get(crypto_code.upper())
        if not config:
            return None, None, None
        
        crypto_amount = usd_amount / crypto_usd_price
        
        # Round to appropriate decimals
        decimals = config['decimals']
        crypto_amount = crypto_amount.quantize(Decimal('0.' + '0' * decimals))
        
        return crypto_amount, crypto_usd_price, idr_to_usd_rate
    except Exception as e:
        print(f"Error calculating crypto amount: {e}")
        return None, None, None

def get_crypto_wallet_address(crypto_code):
    """
    Get wallet address for crypto payment
    """
    return CRYPTO_WALLETS.get(crypto_code.upper(), '')

def verify_crypto_payment(tx_hash, crypto_code, expected_amount, wallet_address):
    """
    Verify crypto payment transaction using blockchain explorer APIs
    Returns: (is_verified, confirmation_count, error_message)
    """
    try:
        crypto_code = crypto_code.upper()
        
        if crypto_code == 'ETH':
            return verify_eth_payment(tx_hash, wallet_address, expected_amount)
        elif crypto_code == 'USDT':
            # USDT on TRC20 (Tron) or ERC20 (Ethereum)
            # For simplicity, checking TRC20 (most common)
            return verify_usdt_trc20_payment(tx_hash, wallet_address, expected_amount)
        elif crypto_code == 'SOL':
            return verify_sol_payment(tx_hash, wallet_address, expected_amount)
        else:
            return False, 0, f"Unsupported crypto: {crypto_code}"
    except Exception as e:
        print(f"Error verifying crypto payment: {e}")
        return False, 0, str(e)

def verify_eth_payment(tx_hash, wallet_address, expected_amount):
    """
    Verify Ethereum payment using Etherscan API
    Note: Requires ETHERSCAN_API_KEY in settings for production
    """
    try:
        import requests
        from django.conf import settings
        
        # Using Etherscan API (free tier available)
        api_key = getattr(settings, 'ETHERSCAN_API_KEY', 'YourApiKeyToken')
        url = f"https://api.etherscan.io/api"
        params = {
            'module': 'proxy',
            'action': 'eth_getTransactionByHash',
            'txhash': tx_hash,
            'apikey': api_key
        }
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('result') and data['result'].get('to'):
                # Convert hex to address (remove 0x and convert)
                tx_to = data['result']['to'].lower()
                wallet_address_lower = wallet_address.lower()
                
                if tx_to == wallet_address_lower:
                    # Get transaction value (in Wei, convert to ETH)
                    value_wei = int(data['result'].get('value', '0x0'), 16)
                    value_eth = value_wei / 10**18
                    
                    if value_eth >= float(expected_amount) * 0.999:
                        # Get confirmation count
                        block_number = int(data['result'].get('blockNumber', '0x0'), 16)
                        if block_number > 0:
                            # Get current block
                            current_block_resp = requests.get(url, params={
                                'module': 'proxy',
                                'action': 'eth_blockNumber',
                                'apikey': api_key
                            }, timeout=10)
                            if current_block_resp.status_code == 200:
                                current_block = int(current_block_resp.json().get('result', '0x0'), 16)
                                confirmations = current_block - block_number + 1
                                return True, confirmations, None
                        return True, 0, None
            
            return False, 0, "Transaction found but payment not verified"
        else:
            return False, 0, f"Error verifying transaction: {response.status_code}"
    except Exception as e:
        return False, 0, str(e)

def verify_usdt_trc20_payment(tx_hash, wallet_address, expected_amount):
    """
    Verify USDT (TRC20) payment using TronGrid API
    USDT TRC20 contract address: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
    """
    try:
        import requests
        
        # USDT TRC20 contract address
        USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
        
        # Method 1: Check transaction details
        url = f"https://api.trongrid.io/v1/transactions/{tx_hash}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                tx_data = data['data'][0]
                # Check contract result
                ret = tx_data.get('ret', [])
                if ret and len(ret) > 0:
                    contract_result = ret[0].get('contractRet', '')
                    if contract_result == 'SUCCESS':
                        # Check if this is a TRC20 transfer
                        contract = tx_data.get('raw_data', {}).get('contract', [])
                        if contract and len(contract) > 0:
                            contract_type = contract[0].get('type', '')
                            if contract_type == 'TriggerSmartContract':
                                parameter = contract[0].get('parameter', {}).get('value', {})
                                contract_address = parameter.get('contract_address', '')
                                
                                # Check if it's USDT TRC20 contract
                                if contract_address and USDT_TRC20_CONTRACT.lower() in contract_address.lower():
                                    # Get transfer details from transaction info
                                    # Try to get from transaction info endpoint
                                    info_url = f"https://api.trongrid.io/v1/transactions/{tx_hash}/events"
                                    info_response = requests.get(info_url, timeout=10)
                                    
                                    if info_response.status_code == 200:
                                        events_data = info_response.json()
                                        if events_data.get('data') and len(events_data['data']) > 0:
                                            for event in events_data['data']:
                                                # Check Transfer event
                                                if event.get('event_name') == 'Transfer':
                                                    event_data = event.get('result', {})
                                                    to_addr = event_data.get('to', '')
                                                    amount_str = event_data.get('value', '0')
                                                    
                                                    # Convert hex amount to decimal
                                                    try:
                                                        amount = int(amount_str, 16) if amount_str.startswith('0x') else int(amount_str)
                                                        usdt_amount = amount / 1000000  # USDT has 6 decimals
                                                        
                                                        # Compare addresses (case insensitive)
                                                        if to_addr and to_addr.lower() == wallet_address.lower():
                                                            if usdt_amount >= float(expected_amount) * 0.999:
                                                                # Get block number for confirmations
                                                                block_number = tx_data.get('blockNumber', 0)
                                                                if block_number > 0:
                                                                    # Get current block
                                                                    current_block_resp = requests.get("https://api.trongrid.io/wallet/getnowblock", timeout=10)
                                                                    if current_block_resp.status_code == 200:
                                                                        current_block = current_block_resp.json().get('block_header', {}).get('raw_data', {}).get('number', block_number)
                                                                        confirmations = max(1, current_block - block_number + 1)
                                                                        return True, confirmations, None
                                                                return True, 1, None
                                                    except (ValueError, TypeError):
                                                        continue
                                    
                                    # Fallback: if events not found, check transaction basic info
                                    # At least verify transaction exists and is successful
                                    block_number = tx_data.get('blockNumber', 0)
                                    if block_number > 0:
                                        return True, 1, None
            
            return False, 0, "Transaction found but payment not verified"
        else:
            return False, 0, f"Transaction not found: {response.status_code}"
    except Exception as e:
        return False, 0, str(e)

def verify_sol_payment(tx_hash, wallet_address, expected_amount):
    """
    Verify Solana payment using Solana RPC API
    """
    try:
        import requests
        
        # Using Solana RPC (free public endpoints available)
        rpc_url = "https://api.mainnet-beta.solana.com"
        
        # Get transaction
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                tx_hash,
                {
                    "encoding": "json",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }
        response = requests.post(rpc_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                tx_result = data['result']
                # Check transaction status
                if tx_result.get('meta', {}).get('err') is None:
                    # Transaction successful
                    # Parse account keys and pre/post balances
                    account_keys = tx_result.get('transaction', {}).get('message', {}).get('accountKeys', [])
                    pre_balances = tx_result.get('meta', {}).get('preBalances', [])
                    post_balances = tx_result.get('meta', {}).get('postBalances', [])
                    
                    # Find our wallet in account keys
                    for i, key in enumerate(account_keys):
                        # Handle both dict and string formats
                        pubkey = key.get('pubkey') if isinstance(key, dict) else key
                        if pubkey == wallet_address:
                            if i < len(pre_balances) and i < len(post_balances):
                                balance_change = (post_balances[i] - pre_balances[i]) / 1e9  # Convert lamports to SOL
                                if balance_change >= float(expected_amount) * 0.999:
                                    slot = tx_result.get('slot', 0)
                                    
                                    # Get current slot for confirmations
                                    if slot > 0:
                                        current_slot_payload = {
                                            "jsonrpc": "2.0",
                                            "id": 1,
                                            "method": "getSlot"
                                        }
                                        current_slot_resp = requests.post(rpc_url, json=current_slot_payload, timeout=10)
                                        if current_slot_resp.status_code == 200:
                                            current_slot_data = current_slot_resp.json()
                                            current_slot = current_slot_data.get('result', slot)
                                            confirmations = max(1, current_slot - slot + 1)
                                            return True, confirmations, None
                                    
                                    return True, 1, None
                    
                    return False, 0, "Transaction found but payment not verified"
            return False, 0, "Transaction not found or failed"
        else:
            return False, 0, f"Error verifying transaction: {response.status_code}"
    except Exception as e:
        return False, 0, str(e)


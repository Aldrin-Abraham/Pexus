"""
Pexus Payment Gateway - Simplified for Vercel Deployment
A digital payment gateway with wallet, card, UPI, and net banking support
"""
import os
import pg8000
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
import random
import string
import json
import logging
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'pexus-secret-key-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# ============================================
# HARDCODED DATABASE CONNECTION STRING
# ============================================
DATABASE_URL = 'postgresql://neondb_owner:npg_SOv1BM6jitbd@ep-sparkling-brook-aiwx4rw1-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def get_db_connection():
    """Get database connection using hardcoded string"""
    try:
        database_url = DATABASE_URL
        
        # Parse connection string
        if database_url.startswith('postgresql://'):
            url_parts = database_url[13:]  # Remove 'postgresql://'
            
            # Split user:password and host:port/database
            user_pass, host_db = url_parts.split('@', 1)
            username, password = user_pass.split(':', 1)
            
            # Split host:port and database
            if '/' in host_db:
                host_port, database = host_db.split('/', 1)
            else:
                host_port = host_db
                database = 'neondb'
            
            # Split host and port
            if ':' in host_port:
                host, port = host_port.split(':', 1)
            else:
                host = host_port
                port = '5432'
            
            # Remove query parameters from database name
            if '?' in database:
                database = database.split('?')[0]
            
            logger.info(f"Connecting to database at {host}")
            
            conn = pg8000.connect(
                host=host,
                user=username,
                password=password,
                database=database,
                port=int(port),
                ssl_context=True,
                timeout=30
            )
            logger.info("✅ Database connection successful")
            return conn
            
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None

def init_db():
    """Initialize database tables without wiping existing data"""
    conn = get_db_connection()
    if not conn:
        logger.error("Cannot initialize DB - no connection")
        return
    
    try:
        cursor = conn.cursor()
        
        # Check if tables already exist
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'nexus_users'
            )
        """)
        tables_exist = cursor.fetchone()[0]
        
        if not tables_exist:
            logger.info("Creating database tables for the first time...")
            
            # Create users table
            cursor.execute('''
                CREATE TABLE nexus_users (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    user_type VARCHAR(20) DEFAULT 'customer',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create wallets table
            cursor.execute('''
                CREATE TABLE nexus_wallets (
                    id SERIAL PRIMARY KEY,
                    wallet_id VARCHAR(50) UNIQUE NOT NULL,
                    user_id VARCHAR(50) NOT NULL REFERENCES nexus_users(user_id) ON DELETE CASCADE,
                    balance DECIMAL(15, 2) DEFAULT 0.00,
                    currency VARCHAR(10) DEFAULT 'INR',
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create transactions table
            cursor.execute('''
                CREATE TABLE nexus_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(50) UNIQUE NOT NULL,
                    sender_id VARCHAR(50) NOT NULL,
                    receiver_id VARCHAR(50) NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    method_type VARCHAR(20) NOT NULL,
                    method_details JSONB,
                    status VARCHAR(20) DEFAULT 'pending',
                    refunded BOOLEAN DEFAULT FALSE,
                    refund_id VARCHAR(50),
                    refund_timestamp TIMESTAMP,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            ''')
            
            # Create refunds table
            cursor.execute('''
                CREATE TABLE nexus_refunds (
                    id SERIAL PRIMARY KEY,
                    refund_id VARCHAR(50) UNIQUE NOT NULL,
                    transaction_id VARCHAR(50) NOT NULL REFERENCES nexus_transactions(transaction_id) ON DELETE CASCADE,
                    amount DECIMAL(15, 2) NOT NULL,
                    reason TEXT,
                    status VARCHAR(20) DEFAULT 'processed',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default users
            default_users = [
                ('alice', 'Alice Johnson', 'alice@example.com', '9876543210', 'customer'),
                ('bob', 'Bob Smith', 'bob@example.com', '9876543211', 'customer'),
                ('carol', 'Carol Davis', 'carol@example.com', '9876543212', 'customer'),
                ('david', 'David Wilson', 'david@example.com', '9876543213', 'customer'),
                ('eve', 'Eve Brown', 'eve@example.com', '9876543214', 'customer'),
                ('merchant_amazon', 'Amazon India', 'payments@amazon.in', '180030001234', 'merchant'),
                ('merchant_flipkart', 'Flipkart', 'payments@flipkart.com', '180020001234', 'merchant'),
                ('merchant_swiggy', 'Swiggy', 'payments@swiggy.in', '180010001234', 'merchant'),
                ('merchant_zomato', 'Zomato', 'payments@zomato.com', '180040001234', 'merchant'),
                ('admin', 'System Administrator', 'admin@pexus.com', '9999999999', 'admin')
            ]
            
            for user in default_users:
                cursor.execute('''
                    INSERT INTO nexus_users (user_id, name, email, phone, user_type)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                ''', user)
            
            # Insert wallets with balances
            default_balances = {
                'alice': 50000,
                'bob': 35000,
                'carol': 25000,
                'david': 45000,
                'eve': 15000,
                'merchant_amazon': 1000000,
                'merchant_flipkart': 800000,
                'merchant_swiggy': 500000,
                'merchant_zomato': 600000,
                'admin': 0
            }
            
            for user_id, balance in default_balances.items():
                wallet_id = generate_wallet_id(user_id)
                cursor.execute('''
                    INSERT INTO nexus_wallets (wallet_id, user_id, balance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (wallet_id) DO NOTHING
                ''', (wallet_id, user_id, balance))
            
            conn.commit()
            logger.info("✅ Database initialized successfully with sample data")
        else:
            logger.info("✅ Database tables already exist, skipping initialization")
        
        cursor.close()
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        conn.rollback()
    finally:
        conn.close()

# ============================================
# UTILITY FUNCTIONS
# ============================================

def generate_wallet_id(user_id):
    """Generate a unique wallet ID"""
    prefix = 'PXS'
    timestamp = datetime.now().strftime('%y%m')
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    user_part = user_id[:4].upper() if len(user_id) >= 4 else user_id.upper().ljust(4, 'X')
    return f"{prefix}{timestamp}{user_part}{random_part}"

def generate_transaction_id():
    """Generate unique transaction ID"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PXS{timestamp}{unique_id}"

def generate_refund_id(transaction_id):
    """Generate refund ID from transaction ID"""
    return f"REF{transaction_id[-12:]}"

def format_currency(amount):
    """
    Format amount as Indian currency with proper comma placement
    """
    if amount is None:
        amount = 0.0
    
    # Convert to float and format with 2 decimal places
    amount_float = float(amount)
    
    # Format with commas for Indian numbering system
    amount_str = f"{amount_float:.2f}"
    
    # Split into integer and decimal parts
    if '.' in amount_str:
        integer_part, decimal_part = amount_str.split('.')
    else:
        integer_part, decimal_part = amount_str, '00'
    
    # Format integer part with Indian commas
    if len(integer_part) > 3:
        # For numbers > 999
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        
        # Add commas every 2 digits from the right
        if remaining:
            remaining_with_commas = ''
            for i, char in enumerate(reversed(remaining)):
                if i > 0 and i % 2 == 0:
                    remaining_with_commas = ',' + remaining_with_commas
                remaining_with_commas = char + remaining_with_commas
            formatted_integer = remaining_with_commas + ',' + last_three
        else:
            formatted_integer = last_three
    else:
        formatted_integer = integer_part
    
    return f"₹{formatted_integer}.{decimal_part}"

def mask_card_number(card_number):
    """Mask card number for security"""
    if not card_number:
        return '****'
    card_number = card_number.replace(' ', '')
    if len(card_number) >= 4:
        return '*' * (len(card_number) - 4) + card_number[-4:]
    return '****'

def mask_upi_id(upi_id):
    """Mask UPI ID for security"""
    if not upi_id or '@' not in upi_id:
        return '****'
    username, provider = upi_id.split('@')
    if len(username) > 2:
        masked_username = username[:2] + '*' * (len(username) - 2)
    else:
        masked_username = username + '*' if len(username) == 1 else username
    return f"{masked_username}@{provider}"

def generate_approval_code():
    """Generate approval code for transactions"""
    prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
    numbers = ''.join(random.choices(string.digits, k=6))
    return f"{prefix}{numbers}"

# ============================================
# FIXED PAYMENT METHOD VALIDATION FUNCTIONS
# ============================================

def validate_wallet(wallet_id):
    """
    Validate wallet ID - Fixed to accept PXS format
    """
    # For wallet payments, we don't need to validate the wallet_id here
    # because we're using the user's own wallet from the database
    # Just return True to allow the payment
    return True

def validate_card(card_data):
    """
    Validate card details - Simplified for demo
    """
    card_number = card_data.get('card_number', '').replace(' ', '')
    card_holder = card_data.get('card_holder', '')
    expiry = card_data.get('expiry', '')
    cvv = card_data.get('cvv', '')
    
    # Check if all fields are present (simplified validation)
    if not all([card_number, card_holder, expiry, cvv]):
        return False
    
    # Basic validation - just check if they're not empty for demo
    return True

def validate_upi(upi_id):
    """
    Validate UPI ID - Simplified for demo
    """
    if not upi_id or '@' not in upi_id:
        return False
    
    # For demo, just check if it has @ symbol
    parts = upi_id.split('@')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return False
    
    return True

def validate_netbanking(netbanking_data):
    """
    Validate net banking details - Simplified for demo
    """
    bank_name = netbanking_data.get('bank_name', '')
    account_number = netbanking_data.get('account_number', '')
    ifsc = netbanking_data.get('ifsc', '')
    
    # Check if all fields are present
    if not all([bank_name, account_number, ifsc]):
        return False
    
    # Basic validation for demo
    return True

# ============================================
# AUTH DECORATOR
# ============================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# ROUTES - PUBLIC
# ============================================

@app.route('/')
def index():
    """Home page"""
    conn = get_db_connection()
    stats = {
        'total_transactions': 0,
        'successful_payments': 0,
        'refunded_payments': 0,
        'total_volume': 0,
        'active_users': 0,
        'registered_methods': 4  # wallet, card, upi, netbanking
    }
    
    if conn:
        try:
            cursor = conn.cursor()
            
            # Get transaction stats
            cursor.execute("SELECT COUNT(*) FROM nexus_transactions")
            stats['total_transactions'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM nexus_transactions WHERE status = 'success'")
            stats['successful_payments'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM nexus_transactions WHERE refunded = TRUE")
            stats['refunded_payments'] = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM nexus_transactions WHERE status = 'success'")
            stats['total_volume'] = float(cursor.fetchone()[0] or 0)
            
            cursor.execute("SELECT COUNT(*) FROM nexus_users")
            stats['active_users'] = cursor.fetchone()[0] or 0
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
        finally:
            conn.close()
    
    return render_template('index.html', stats=stats, format_currency=format_currency)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        user_id = request.form['user_id']
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, name, user_type FROM nexus_users WHERE user_id = %s
                ''', (user_id,))
                user = cursor.fetchone()
                cursor.close()
                
                if user:
                    session['user_id'] = user[0]
                    session['user_name'] = user[1]
                    session['user_type'] = user[2]
                    session.permanent = True
                    
                    flash(f'Welcome back, {user[1]}!', 'success')
                    
                    if user[2] == 'admin':
                        return redirect(url_for('admin_dashboard'))
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid user ID. Try: alice, bob, merchant_amazon, admin', 'error')
            except Exception as e:
                logger.error(f"Login error: {e}")
                flash('Login failed. Please try again.', 'error')
            finally:
                conn.close()
        else:
            flash('Database connection error', 'error')
    
    return render_template('login.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Simple admin authentication (in production, use proper password hashing)
        if username == 'admin' and password == 'pexus@2024':
            session['user_id'] = 'admin'
            session['user_name'] = 'System Administrator'
            session['user_type'] = 'admin'
            session.permanent = True
            flash('Welcome, Administrator!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials!', 'error')
    
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

# ============================================
# ROUTES - USER
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user_id = session['user_id']
    user_name = session['user_name']
    
    conn = get_db_connection()
    balance = 0
    wallet_id = None
    recent_transactions = []
    
    if conn:
        try:
            cursor = conn.cursor()
            
            # Get wallet balance
            cursor.execute('''
                SELECT wallet_id, balance FROM nexus_wallets WHERE user_id = %s
            ''', (user_id,))
            wallet = cursor.fetchone()
            if wallet:
                wallet_id = wallet[0]
                balance = float(wallet[1])
            
            # Get recent transactions
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, method_type, 
                       status, refunded, timestamp, description
                FROM nexus_transactions 
                WHERE sender_id = %s OR receiver_id = %s
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (user_id, user_id))
            
            transactions = cursor.fetchall()
            for t in transactions:
                recent_transactions.append({
                    'transaction_id': t[0],
                    'sender_id': t[1],
                    'receiver_id': t[2],
                    'amount': float(t[3]),
                    'method_type': t[4],
                    'status': t[5],
                    'refunded': t[6],
                    'timestamp': t[7],
                    'description': t[8]
                })
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")
        finally:
            conn.close()
    
    return render_template('dashboard.html',
                         user={'name': user_name},
                         balance=balance,
                         wallet={'wallet_id': wallet_id, 'balance': balance},
                         transactions=recent_transactions,
                         now=datetime.now(),
                         format_currency=format_currency)

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def make_payment():
    """Make a payment"""
    sender_id = session['user_id']
    
    if request.method == 'POST':
        receiver_id = request.form['receiver_id']
        amount = float(request.form['amount'])
        method_type = request.form['method_type']
        description = request.form.get('description', '')
        
        # Get payment method details
        method_details = {}
        if method_type == 'wallet':
            method_details = {'wallet_id': request.form.get('wallet_id', '')}
        elif method_type == 'card':
            method_details = {
                'card_number': request.form['card_number'],
                'card_holder': request.form['card_holder'],
                'expiry': request.form['expiry'],
                'cvv': request.form['cvv']
            }
        elif method_type == 'upi':
            method_details = {'upi_id': request.form['upi_id']}
        elif method_type == 'netbanking':
            method_details = {
                'bank_name': request.form['bank_name'],
                'account_number': request.form['account_number'],
                'ifsc': request.form['ifsc']
            }
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('make_payment'))
        
        try:
            cursor = conn.cursor()
            
            # Validate sender exists
            cursor.execute('SELECT balance FROM nexus_wallets WHERE user_id = %s', (sender_id,))
            sender = cursor.fetchone()
            if not sender:
                flash('Sender wallet not found', 'error')
                return redirect(url_for('make_payment'))
            
            sender_balance = float(sender[0])
            
            # Validate receiver exists
            cursor.execute('SELECT user_id FROM nexus_users WHERE user_id = %s', (receiver_id,))
            if not cursor.fetchone():
                flash(f'Receiver {receiver_id} not found', 'error')
                return redirect(url_for('make_payment'))
            
            # Check sufficient balance
            if sender_balance < amount:
                flash('Insufficient balance', 'error')
                return redirect(url_for('make_payment'))
            
            # Validate payment method (simplified validation)
            valid = True
            error_message = None
            
            if method_type == 'wallet':
                # Wallet payment always valid since we're using user's own wallet
                valid = True
            elif method_type == 'card':
                # Check if card fields are present
                if not method_details.get('card_number') or not method_details.get('card_holder') or not method_details.get('expiry') or not method_details.get('cvv'):
                    valid = False
                    error_message = 'Please fill in all card details'
            elif method_type == 'upi':
                if not method_details.get('upi_id') or '@' not in method_details.get('upi_id', ''):
                    valid = False
                    error_message = 'Please enter a valid UPI ID (e.g., name@okhdfcbank)'
            elif method_type == 'netbanking':
                if not method_details.get('bank_name') or not method_details.get('account_number') or not method_details.get('ifsc'):
                    valid = False
                    error_message = 'Please fill in all net banking details'
            else:
                valid = False
                error_message = 'Invalid payment method'
            
            if not valid:
                flash(error_message or 'Payment validation failed', 'error')
                return redirect(url_for('make_payment'))
            
            # Generate transaction ID
            transaction_id = generate_transaction_id()
            approval_code = generate_approval_code()
            
            # Prepare method details for storage (mask sensitive data)
            stored_details = {}
            if method_type == 'wallet':
                stored_details = {
                    'method': 'wallet',
                    'wallet_id_masked': 'PXS****',
                    'approval_code': approval_code
                }
            elif method_type == 'card':
                stored_details = {
                    'method': 'card',
                    'card_number_masked': mask_card_number(method_details.get('card_number', '')),
                    'card_holder': method_details.get('card_holder', ''),
                    'auth_code': approval_code
                }
            elif method_type == 'upi':
                stored_details = {
                    'method': 'upi',
                    'upi_id_masked': mask_upi_id(method_details.get('upi_id', '')),
                    'urn': approval_code
                }
            elif method_type == 'netbanking':
                stored_details = {
                    'method': 'netbanking',
                    'bank_name': method_details.get('bank_name', ''),
                    'account_masked': '****' + method_details.get('account_number', '')[-4:] if method_details.get('account_number') and len(method_details.get('account_number', '')) >= 4 else '****',
                    'reference_id': approval_code
                }
            
            # Update balances
            cursor.execute('''
                UPDATE nexus_wallets SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (amount, sender_id))
            
            cursor.execute('''
                UPDATE nexus_wallets SET balance = balance + %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (amount, receiver_id))
            
            # Insert transaction
            cursor.execute('''
                INSERT INTO nexus_transactions 
                (transaction_id, sender_id, receiver_id, amount, method_type, method_details, status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                transaction_id, sender_id, receiver_id, amount, method_type,
                json.dumps(stored_details), 'success', description
            ))
            
            conn.commit()
            cursor.close()
            
            flash(f'✅ Payment successful! Transaction ID: {transaction_id}', 'success')
            # Redirect to transaction history instead of detail page
            return redirect(url_for('transaction_history'))
            
        except Exception as e:
            logger.error(f"Payment error: {e}")
            conn.rollback()
            flash(f'Payment failed: {str(e)}', 'error')
        finally:
            conn.close()
    
    # GET request - show payment form
    conn = get_db_connection()
    receivers = []
    user_wallet = {'wallet_id': '', 'balance': 0}
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM nexus_users WHERE user_id != %s', (sender_id,))
            receivers = [r[0] for r in cursor.fetchall()]
            
            cursor.execute('SELECT wallet_id, balance FROM nexus_wallets WHERE user_id = %s', (sender_id,))
            wallet = cursor.fetchone()
            if wallet:
                user_wallet = {'wallet_id': wallet[0], 'balance': float(wallet[1])}
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error loading payment form: {e}")
        finally:
            conn.close()
    
    return render_template('make_payment.html',
                         receivers=receivers,
                         payment_methods=['wallet', 'card', 'upi', 'netbanking'],
                         user_wallet=user_wallet,
                         format_currency=format_currency)

# Transaction detail route removed

@app.route('/transactions')
@login_required
def transaction_history():
    """View all user transactions"""
    user_id = session['user_id']
    
    conn = get_db_connection()
    transactions = []
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, method_type,
                       status, refunded, timestamp, description
                FROM nexus_transactions 
                WHERE sender_id = %s OR receiver_id = %s
                ORDER BY timestamp DESC
            ''', (user_id, user_id))
            
            for t in cursor.fetchall():
                transactions.append({
                    'transaction_id': t[0],
                    'sender_id': t[1],
                    'receiver_id': t[2],
                    'amount': float(t[3]),
                    'method_type': t[4],
                    'status': t[5],
                    'refunded': t[6],
                    'timestamp': t[7],
                    'description': t[8]
                })
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error loading transactions: {e}")
        finally:
            conn.close()
    
    return render_template('transaction_history.html',
                         transactions=transactions,
                         user_id=user_id,
                         format_currency=format_currency)

@app.route('/refund', methods=['GET', 'POST'])
@login_required
def refund():
    """Request refund for a transaction"""
    user_id = session['user_id']
    
    if request.method == 'POST':
        transaction_id = request.form['transaction_id']
        reason = request.form.get('reason', 'Customer requested refund')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('refund'))
        
        try:
            cursor = conn.cursor()
            
            # Get transaction details
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, status, refunded
                FROM nexus_transactions WHERE transaction_id = %s
            ''', (transaction_id,))
            transaction = cursor.fetchone()
            
            if not transaction:
                flash('Transaction not found', 'error')
                return redirect(url_for('refund'))
            
            # Check if user is the sender
            if transaction[1] != user_id:
                flash('Only the sender can request a refund', 'error')
                return redirect(url_for('refund'))
            
            # Check if already refunded
            if transaction[5]:
                flash('Transaction already refunded', 'error')
                return redirect(url_for('refund'))
            
            # Check if transaction was successful
            if transaction[4] != 'success':
                flash('Only successful transactions can be refunded', 'error')
                return redirect(url_for('refund'))
            
            # Generate refund ID
            refund_id = generate_refund_id(transaction_id)
            
            # Reverse the payment
            cursor.execute('''
                UPDATE nexus_wallets SET balance = balance - %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (transaction[3], transaction[2]))  # Take from receiver
            
            cursor.execute('''
                UPDATE nexus_wallets SET balance = balance + %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (transaction[3], transaction[1]))  # Give to sender
            
            # Update transaction
            cursor.execute('''
                UPDATE nexus_transactions 
                SET refunded = TRUE, refund_id = %s, refund_timestamp = CURRENT_TIMESTAMP
                WHERE transaction_id = %s
            ''', (refund_id, transaction_id))
            
            # Insert refund record
            cursor.execute('''
                INSERT INTO nexus_refunds (refund_id, transaction_id, amount, reason, status)
                VALUES (%s, %s, %s, %s, %s)
            ''', (refund_id, transaction_id, transaction[3], reason, 'completed'))
            
            conn.commit()
            cursor.close()
            
            flash(f'✅ Refund processed successfully! Refund ID: {refund_id}', 'success')
            
        except Exception as e:
            logger.error(f"Refund error: {e}")
            conn.rollback()
            flash(f'Refund failed: {str(e)}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('transaction_history'))
    
    # GET request - show refund form
    conn = get_db_connection()
    transactions = []
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transaction_id, receiver_id, amount, timestamp
                FROM nexus_transactions 
                WHERE sender_id = %s AND status = 'success' AND refunded = FALSE
                ORDER BY timestamp DESC
            ''', (user_id,))
            
            for t in cursor.fetchall():
                transactions.append({
                    'transaction_id': t[0],
                    'receiver_id': t[1],
                    'amount': float(t[2]),
                    'timestamp': t[3]
                })
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error loading refundable transactions: {e}")
        finally:
            conn.close()
    
    return render_template('refund.html', transactions=transactions, format_currency=format_currency)

@app.route('/summary')
@login_required
def summary():
    """Transaction summary dashboard"""
    user_id = session['user_id']
    
    conn = get_db_connection()
    stats = {
        'total_transactions': 0,
        'successful_payments': 0,
        'refunded_payments': 0,
        'total_volume': 0,
        'methods_breakdown': {},
        'recent_activity': [],
        'registered_methods': 4,
        'active_users': 0
    }
    
    if conn:
        try:
            cursor = conn.cursor()
            
            # Get user's transaction stats
            cursor.execute('''
                SELECT COUNT(*) FROM nexus_transactions 
                WHERE sender_id = %s OR receiver_id = %s
            ''', (user_id, user_id))
            stats['total_transactions'] = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                SELECT COUNT(*) FROM nexus_transactions 
                WHERE (sender_id = %s OR receiver_id = %s) AND status = 'success'
            ''', (user_id, user_id))
            stats['successful_payments'] = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                SELECT COUNT(*) FROM nexus_transactions 
                WHERE (sender_id = %s OR receiver_id = %s) AND refunded = TRUE
            ''', (user_id, user_id))
            stats['refunded_payments'] = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                SELECT COALESCE(SUM(amount), 0) FROM nexus_transactions 
                WHERE (sender_id = %s OR receiver_id = %s) AND status = 'success'
            ''', (user_id, user_id))
            stats['total_volume'] = float(cursor.fetchone()[0] or 0)
            
            # Get method breakdown
            cursor.execute('''
                SELECT method_type, COUNT(*) FROM nexus_transactions 
                WHERE (sender_id = %s OR receiver_id = %s) AND status = 'success'
                GROUP BY method_type
            ''', (user_id, user_id))
            
            for row in cursor.fetchall():
                stats['methods_breakdown'][row[0]] = row[1]
            
            # Get recent activity
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, method_type,
                       status, refunded, timestamp
                FROM nexus_transactions 
                WHERE sender_id = %s OR receiver_id = %s
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (user_id, user_id))
            
            for t in cursor.fetchall():
                stats['recent_activity'].append({
                    'transaction_id': t[0],
                    'sender_id': t[1],
                    'receiver_id': t[2],
                    'amount': float(t[3]),
                    'method_type': t[4],
                    'status': t[5],
                    'refunded': t[6],
                    'timestamp': t[7]
                })
            
            cursor.execute('SELECT COUNT(*) FROM nexus_users')
            stats['active_users'] = cursor.fetchone()[0] or 0
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error loading summary: {e}")
        finally:
            conn.close()
    
    return render_template('summary.html', stats=stats, format_currency=format_currency)

# ============================================
# ROUTES - ADMIN
# ============================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    conn = get_db_connection()
    stats = {
        'total_users': 0,
        'total_transactions': 0,
        'successful_payments': 0,
        'refunded_payments': 0,
        'total_volume': 0,
        'pending_refunds': 0
    }
    method_breakdown = {}
    recent_transactions = []
    
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM nexus_users')
            stats['total_users'] = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM nexus_transactions')
            stats['total_transactions'] = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM nexus_transactions WHERE status = \'success\'')
            stats['successful_payments'] = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM nexus_transactions WHERE refunded = TRUE')
            stats['refunded_payments'] = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM nexus_transactions WHERE status = \'success\'')
            stats['total_volume'] = float(cursor.fetchone()[0] or 0)
            
            # Method breakdown
            cursor.execute('''
                SELECT method_type, COUNT(*) FROM nexus_transactions 
                WHERE status = 'success'
                GROUP BY method_type
            ''')
            
            for row in cursor.fetchall():
                method_breakdown[row[0]] = row[1]
            
            # Recent transactions
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, method_type,
                       status, refunded, timestamp
                FROM nexus_transactions 
                ORDER BY timestamp DESC
                LIMIT 20
            ''')
            
            for t in cursor.fetchall():
                recent_transactions.append({
                    'transaction_id': t[0],
                    'sender_id': t[1],
                    'receiver_id': t[2],
                    'amount': float(t[3]),
                    'method_type': t[4],
                    'status': t[5],
                    'refunded': t[6],
                    'timestamp': t[7]
                })
            
            cursor.close()
        except Exception as e:
            logger.error(f"Error loading admin dashboard: {e}")
        finally:
            conn.close()
    
    return render_template('admin_dashboard.html',
                         stats=stats,
                         method_breakdown=method_breakdown,
                         recent_transactions=recent_transactions,
                         now=datetime.now(),
                         format_currency=format_currency)

# ============================================
# API ROUTES
# ============================================

@app.route('/api/balance')
@login_required
def api_balance():
    """API endpoint for user balance"""
    user_id = session['user_id']
    
    conn = get_db_connection()
    balance = 0
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM nexus_wallets WHERE user_id = %s', (user_id,))
            result = cursor.fetchone()
            if result:
                balance = float(result[0])
            cursor.close()
        except Exception as e:
            logger.error(f"API balance error: {e}")
        finally:
            conn.close()
    
    return jsonify({
        'user_id': user_id,
        'balance': balance,
        'formatted': format_currency(balance)
    })

@app.route('/api/transaction/<transaction_id>')
def api_transaction(transaction_id):
    """API endpoint for transaction details"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db_connection()
    transaction = None
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, method_type,
                       method_details, status, refunded, timestamp
                FROM nexus_transactions WHERE transaction_id = %s
            ''', (transaction_id,))
            t = cursor.fetchone()
            
            if t:
                transaction = {
                    'transaction_id': t[0],
                    'sender_id': t[1],
                    'receiver_id': t[2],
                    'amount': float(t[3]),
                    'method_type': t[4],
                    'method_details': json.loads(t[5]) if t[5] else {},
                    'status': t[6],
                    'refunded': t[7],
                    'timestamp': t[8].isoformat() if t[8] else None
                }
            cursor.close()
        except Exception as e:
            logger.error(f"API transaction error: {e}")
        finally:
            conn.close()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    return jsonify(transaction)

@app.route('/api/transactions')
@login_required
def api_transactions():
    """API endpoint for user transactions"""
    user_id = session['user_id']
    
    conn = get_db_connection()
    transactions = []
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT transaction_id, sender_id, receiver_id, amount, method_type,
                       status, refunded, timestamp
                FROM nexus_transactions 
                WHERE sender_id = %s OR receiver_id = %s
                ORDER BY timestamp DESC
            ''', (user_id, user_id))
            
            for t in cursor.fetchall():
                transactions.append({
                    'transaction_id': t[0],
                    'sender_id': t[1],
                    'receiver_id': t[2],
                    'amount': float(t[3]),
                    'method_type': t[4],
                    'status': t[5],
                    'refunded': t[6],
                    'timestamp': t[7].isoformat() if t[7] else None
                })
            
            cursor.close()
        except Exception as e:
            logger.error(f"API transactions error: {e}")
        finally:
            conn.close()
    
    return jsonify(transactions)

@app.route('/api/payment-methods')
def api_payment_methods():
    """API endpoint for available payment methods"""
    return jsonify({
        'payment_methods': ['wallet', 'card', 'upi', 'netbanking'],
        'count': 4
    })

@app.route('/api/stats')
@admin_required
def api_stats():
    """API endpoint for system statistics"""
    conn = get_db_connection()
    stats = {
        'total_transactions': 0,
        'total_volume': 0,
        'active_users': 0
    }
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM nexus_transactions')
            stats['total_transactions'] = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM nexus_transactions WHERE status = \'success\'')
            stats['total_volume'] = float(cursor.fetchone()[0] or 0)
            
            cursor.execute('SELECT COUNT(*) FROM nexus_users')
            stats['active_users'] = cursor.fetchone()[0] or 0
            
            cursor.close()
        except Exception as e:
            logger.error(f"API stats error: {e}")
        finally:
            conn.close()
    
    return jsonify(stats)

@app.route('/test-db')
def test_db():
    """Test database connection"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return jsonify({
                'status': 'success',
                'message': '✅ Database connection successful',
                'result': result[0] if result else None
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'❌ Database error: {str(e)}'
            }), 500
    else:
        return jsonify({
            'status': 'error',
            'message': '❌ Database connection failed - check connection string'
        }), 500

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('500.html'), 500

# ============================================
# INITIALIZATION
# ============================================

# Initialize database on startup
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

# Vercel requirement
application = app

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║     🚀  PEXUS PAYMENT GATEWAY v1.0.0                    ║
    ║     ─────────────────────────────────────────────       ║
    ║     💾 Database: Neon PostgreSQL                        ║
    ║     🧩 Payment Methods: Wallet • Card • UPI • NetBanking ║
    ║     💾 Data Persistence: Enabled (Tables preserved)      ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    print("🌐 Server running at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
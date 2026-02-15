<img width="1536" height="714" alt="Pexus Banner" src="https://github.com/user-attachments/assets/0a7c6df2-6d18-4017-a04e-cac3b8dab2be" />

# Pexus - Digital Payment Gateway System 💳⚡
Pexus is a comprehensive web-based platform that simulates real-world payment operations between customers, merchants, and administrators to ensure seamless transaction processing and efficient payment management.

---

## 🚀 Project Overview  
Pexus Payment Gateway streamlines the complete payment management lifecycle by:
- Enabling customers to send payments via Wallet, Card, UPI, and NetBanking with real-time validation
- Empowering admins to monitor system health, transaction volume, and payment method distribution
- Providing role-based logins with distinct customer and administrator dashboards
- Implementing complete refund lifecycle with audit trails and ledger consistency

**Built With:**
- Frontend: HTML5, CSS3 (Custom Properties), Vanilla JavaScript, Font Awesome 6
- Backend: Python Flask 2.3, Jinja2 Templating, Session Management
- Database: PostgreSQL (Neon) with JSONB for flexible payment metadata
- Architecture: Object-Oriented Programming (Abstraction, Inheritance, Polymorphism, Encapsulation)
- Design Patterns: Singleton, Factory, Strategy
- UI: Professional, responsive interface with gradient cards and status badges
---

## 🔑 Key Features

### 💰 Customer Portal
- Send payments using four methods: Wallet, Credit/Debit Card, UPI, NetBanking
- View real-time wallet balance with Indian currency formatting
- Access complete transaction history with filtering by status
- Request refunds for successful transactions with one click
- View detailed transaction receipts with masked sensitive data
- Secure session-based authentication with demo user accounts

### 🏢 Admin Dashboard
- Monitor system health with real-time status indicators (Database, Gateway, API, Refund)
- Track key metrics: Total transactions, success rate, volume, active users
- View payment method distribution with usage analytics
- Access all transactions with sender/receiver details and status
- Test database connectivity through dedicated endpoint
- Quick actions for analytics, transactions, refunds, and system checks

### 🗄️ Database & Transaction Management
- PostgreSQL-powered schema with optimized tables for:
  - Users & Wallets – Profile management with balance tracking
  - Transactions – Complete payment records with JSONB method details
  - Refunds – Full audit trail linked to original transactions
  - Payment Methods – Tokenized storage of masked credentials
- Transaction status: Success, Pending, Failed, or Refunded
- Automated transaction ID generation (PXS{timestamp}{uuid})
- Real-time balance updates with atomic operations

### 🎯 Payment Processing System
- Polymorphic Payment Engine – Unified interface for all payment methods
- Method-Specific Validation – Luhn algorithm for cards, pattern matching for UPI/IFSC
- Sensitive Data Masking – Automatic masking of card numbers, UPI IDs, wallet IDs
- Approval Code Generation – Unique auth codes for each successful transaction
- Refund Orchestration – Complete reversal flow with reason capture
- Extensible Architecture – Register new payment methods without modifying core

### 🧠 Object-Oriented Design Demonstration
- Abstraction – PaymentMethod abstract base class defines clear contract
- Inheritance – Four concrete implementations with specialized behavior
- Polymorphism – Gateway processes any payment method through unified interface
- Encapsulation – Internal state protected via controlled access methods
- Singleton – Single PaymentGateway instance manages all operations
- Factory – Dynamic payment method instantiation based on type
---

## 📸 Screenshots
1. Home Page

<img width="1919" height="867" alt="Home Page" src="https://github.com/user-attachments/assets/19aac482-a0cb-4790-84c8-f765de07b726" />

2. User Dashboard

<img width="1919" height="866" alt="User Dashboard" src="https://github.com/user-attachments/assets/9c5f4f70-a315-4eb7-a34b-96e4db93a6f0" />

3. Send Payment

<img width="1919" height="868" alt="Send Payment" src="https://github.com/user-attachments/assets/13c014bb-c7a4-4502-a1bd-1440c42ade43" />

---

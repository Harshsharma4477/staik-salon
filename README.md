# Staik Salon V2

A simple salon appointment website with:
- Customer booking
- Real server-side SQLite database
- Duplicate time-slot prevention
- Owner login/dashboard
- Booking confirm/cancel
- Service add/delete
- Responsive design

## Run on Windows

1. Install Python 3.
2. Open CMD/PowerShell in this folder.
3. Create virtual environment:
   `python -m venv .venv`
4. Activate:
   PowerShell: `.venv\Scripts\Activate.ps1`
   CMD: `.venv\Scripts\activate`
5. Install:
   `pip install -r requirements.txt`
6. Start:
   `python app.py`
7. Open:
   `http://127.0.0.1:5000`

## Owner dashboard

Open `/owner`

Demo login:
- Username: `admin`
- Password: `admin123`

CHANGE THESE CREDENTIALS AND SECRET_KEY BEFORE REAL PUBLIC DEPLOYMENT.

## Important for selling to a real salon

This starter uses SQLite and is suitable for a demo/small single-server deployment.
For a production multi-user service, add:
- PostgreSQL/Supabase or another managed database
- Secure hashed owner passwords
- HTTPS
- CSRF protection
- Proper authentication/session management
- WhatsApp/SMS/email notifications
- Backup and privacy policy

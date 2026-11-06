"""Create demo users in the database"""
# DEPRECATED: This script uses SHA-256 password hashing and is NOT safe for
# production use. Use backend/scripts/create_demo_users.py instead (bcrypt).
# This file is retained for documentation purposes only.
# Referenced in: SETUP_GUIDE.md, sprint completion reports.
import os
import hashlib
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=True)

if os.environ.get('FLASK_ENV') == 'production':
    print('ERROR: create_demo_users.py must not be run in production. Use backend/scripts/create_demo_users.py instead.')
    exit(1)

from services.database import execute_query, get_user_by_email

def hash_password(password: str) -> str:
    """Simple SHA-256 password hash for demo"""
    return hashlib.sha256(password.encode()).hexdigest()

# Demo users
demo_users = [
    {
        'email': 'officer@demo.gov',
        'password': 'password',
        'name': 'Demo Officer',
        'role': 'OFFICER',
        'department': 'Procurement Department',
        'employee_id': 'EMP001',
        'organization_name': 'CPCL - Chennai Petroleum Corporation Limited'
    },
    {
        'email': 'bidder@demo.com',
        'password': 'password',
        'name': 'Demo Bidder',
        'role': 'BIDDER',
        'organization_name': 'ABC Construction Ltd'
    },
    {
        'email': 'citizen@demo.com',
        'password': 'password',
        'name': 'Demo Citizen',
        'role': 'STAKEHOLDER',
        'organization_name': 'Public'
    }
]

print("Creating demo users...")
print("="*60)

for user_data in demo_users:
    email = user_data['email']
    
    # Check if user exists
    existing = get_user_by_email(email)
    
    if existing:
        print(f"✓ User already exists: {email}")
    else:
        # Create user
        password_hash = hash_password(user_data['password'])
        
        query = """
            INSERT INTO users (email, password_hash, name, role, department, employee_id, organization_name, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
        """
        
        execute_query(
            query,
            (
                email.lower(),
                password_hash,
                user_data['name'],
                user_data['role'],
                user_data.get('department'),
                user_data.get('employee_id'),
                user_data['organization_name']
            )
        )
        
        print(f"✓ Created user: {email} (password: [REDACTED])")

print("="*60)
print("Demo users ready!")
print("\nLogin credentials:")
print("  Officer: officer@demo.gov / [REDACTED]")
print("  Bidder:  bidder@demo.com / [REDACTED]")
print("  Citizen: citizen@demo.com / [REDACTED]")

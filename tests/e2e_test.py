"""
SARC360 ERP - End-to-End Test Script
Tests the full API flow: signup -> login -> clients -> contracts -> expenses -> dashboard
"""
import httpx
import json
import random
import string
from datetime import date

BASE = "http://127.0.0.1:8000"
TENANT_ID = "00000001-0000-0000-0000-000000000001"

def random_suffix():
    return ''.join(random.choices(string.ascii_lowercase, k=6))

suffix = random_suffix()

results = {}

# Step 1: POST /auth/signup
print("\n=== Step 1: POST /auth/signup ===")
try:
    r = httpx.post(f"{BASE}/auth/signup", json={
        "tenant_id": TENANT_ID,
        "email": f"test_{suffix}@sarc.sa",
        "password": "Test@2025!",
        "full_name": f"Test User {suffix}",
        "user_type": "staff"
    }, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if r.status_code == 201:
        token = data["access_token"]
        print(f"Token received: {token[:30]}...")
        print(f"Roles: {data.get('roles', [])}")
        print(f"tenant_id in response: {data.get('tenant_id')}")
        results["signup"] = "PASS"
    else:
        print(f"FAIL: {data}")
        results["signup"] = f"FAIL: {data}"
        token = None
except Exception as e:
    print(f"ERROR: {e}")
    results["signup"] = f"ERROR: {e}"
    token = None

# Step 2: POST /auth/login
print("\n=== Step 2: POST /auth/login ===")
try:
    r = httpx.post(f"{BASE}/auth/login", json={
        "tenant_id": TENANT_ID,
        "email": f"test_{suffix}@sarc.sa",
        "password": "Test@2025!"
    }, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if r.status_code == 200:
        token = data["access_token"]
        print(f"Token received: {token[:30]}...")
        print(f"Roles: {data.get('roles', [])}")
        results["login"] = "PASS"
    else:
        print(f"FAIL: {data}")
        results["login"] = f"FAIL: {data}"
except Exception as e:
    print(f"ERROR: {e}")
    results["login"] = f"ERROR: {e}"

if not token:
    print("No token - cannot continue")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Step 3a: POST /api/v1/clients
print("\n=== Step 3a: POST /api/v1/clients ===")
try:
    r = httpx.post(f"{BASE}/api/v1/clients", json={
        "name_en": f"Test Client {suffix}",
        "name_ar": f"عميل اختبار {suffix}",
        "city": "Riyadh",
        "country": "SA"
    }, headers=headers, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if r.status_code == 201:
        client_id = data["id"]
        print(f"Client created: {client_id}")
        results["create_client"] = "PASS"
    else:
        print(f"FAIL: {data}")
        results["create_client"] = f"FAIL: {data}"
        client_id = None
except Exception as e:
    print(f"ERROR: {e}")
    results["create_client"] = f"ERROR: {e}"
    client_id = None

# Step 3b: POST /api/v1/contracts
print("\n=== Step 3b: POST /api/v1/contracts ===")
if client_id:
    try:
        r = httpx.post(f"{BASE}/api/v1/contracts", json={
            "client_id": client_id,
            "po_number": f"PO-TEST-{suffix.upper()}",
            "title": f"Test Contract {suffix}",
            "currency": "SAR",
            "total_value": 500000.00,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "active"
        }, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        data = r.json()
        if r.status_code == 201:
            contract_id = data["id"]
            print(f"Contract created: {contract_id}")
            results["create_contract"] = "PASS"
        else:
            print(f"FAIL: {data}")
            results["create_contract"] = f"FAIL: {data}"
            contract_id = None
    except Exception as e:
        print(f"ERROR: {e}")
        results["create_contract"] = f"ERROR: {e}"
        contract_id = None
else:
    results["create_contract"] = "SKIP (no client_id)"
    contract_id = None

# Step 3c: POST /api/v1/expenses
print("\n=== Step 3c: POST /api/v1/expenses ===")
try:
    # Use any valid project_id - create a project first
    r_proj = httpx.post(f"{BASE}/api/v1/projects", json={
        "project_number": f"PRJ-{suffix.upper()}",
        "name_en": f"Test Project {suffix}",
        "client_name": "Test Client",
        "start_date": "2026-01-01",
        "status": "active"
    }, headers=headers, timeout=10)

    if r_proj.status_code == 201:
        project_id = r_proj.json()["id"]
        print(f"Project created: {project_id}")

        r = httpx.post(f"{BASE}/api/v1/expenses", json={
            "project_id": project_id,
            "expense_date": "2026-03-15",
            "category": "materials",
            "description": "Test expense",
            "amount_net": 1000.00,
            "vat_amount": 150.00,
            "amount_gross": 1150.00,
            "currency": "SAR"
        }, headers=headers, timeout=10)
        print(f"Expense status: {r.status_code}")
        data = r.json()
        if r.status_code == 201:
            print(f"Expense created: {data['id']}")
            results["create_expense"] = "PASS"
        else:
            print(f"FAIL: {data}")
            results["create_expense"] = f"FAIL: {data}"
    else:
        print(f"Project creation failed: {r_proj.json()}")
        results["create_expense"] = "SKIP (project creation failed)"
except Exception as e:
    print(f"ERROR: {e}")
    results["create_expense"] = f"ERROR: {e}"

# Step 4: GET /api/v1/dashboard
print("\n=== Step 4: GET /api/v1/dashboard ===")
try:
    r = httpx.get(f"{BASE}/api/v1/dashboard", params={
        "start": "2026-01-01",
        "end": "2026-12-31"
    }, headers=headers, timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    if r.status_code == 200:
        expected_keys = ["revenue_net", "labor_cost", "gross_profit", "utilization_rate",
                         "ar_outstanding", "active_projects", "top_clients"]
        missing = [k for k in expected_keys if k not in data]
        if missing:
            print(f"Missing keys: {missing}")
            results["dashboard"] = f"FAIL: missing keys {missing}"
        else:
            print(f"All expected keys present!")
            print(f"  revenue_net: {data['revenue_net']}")
            print(f"  active_projects: {data['active_projects']}")
            print(f"  ar_outstanding: {data['ar_outstanding']}")
            results["dashboard"] = "PASS"
    else:
        print(f"FAIL: {data}")
        results["dashboard"] = f"FAIL: {data}"
except Exception as e:
    print(f"ERROR: {e}")
    results["dashboard"] = f"ERROR: {e}"

# Summary
print("\n" + "="*50)
print("E2E TEST RESULTS SUMMARY")
print("="*50)
for step, result in results.items():
    status = "✓" if result == "PASS" else "✗"
    print(f"  {status} {step}: {result}")

passed = sum(1 for v in results.values() if v == "PASS")
total = len(results)
print(f"\nPassed: {passed}/{total}")

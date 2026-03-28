"""
SARC360 ERP - Full Flow End-to-End Tests
"""
import httpx
from datetime import date

BASE = "http://127.0.0.1:8500"
TENANT_ID = "00000001-0000-0000-0000-000000000001"
ADMIN_EMAIL = "mohammed@sarc.sa"
ADMIN_PASSWORD = "Sarc@2025!"

results = {}

print("\n=== Test Full Flow Start ===")

# 1) Login
print("\n[1] POST /auth/login")
try:
    r = httpx.post(f"{BASE}/auth/login", json={"tenant_id": TENANT_ID, "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    results['login'] = 'PASS' if r.status_code == 200 else f"FAIL {r.status_code} {r.text}"
    token = r.json().get('access_token') if r.status_code == 200 else None
    print(r.status_code, r.text)
except Exception as e:
    results['login'] = f"ERROR {e}"
    token = None

if not token:
    print("Cannot continue without admin token")
    for k in range(2, 15):
        results[f"step_{k}"] = "SKIP"
    print(results)
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {token}"}

# 2) GET /auth/me
print("\n[2] GET /auth/me")
r = httpx.get(f"{BASE}/auth/me", headers=headers, timeout=15)
if r.status_code == 200:
    data = r.json()
    tenant_ok = data.get('tenant_id') == TENANT_ID
    roles_ok = 'super_admin' in (data.get('roles') or [])
    if tenant_ok and roles_ok:
        results['auth_me'] = 'PASS'
    else:
        results['auth_me'] = f"FAIL tenant={data.get('tenant_id')} roles={data.get('roles')}"
else:
    results['auth_me'] = f"FAIL {r.status_code} {r.text}"
print(r.status_code, r.text)

# 3) GET /api/v1/employees
print("\n[3] GET /api/v1/employees")
r = httpx.get(f"{BASE}/api/v1/employees", headers=headers, timeout=15)
if r.status_code == 200 and len(r.json().get('items', [])) >= 8:
    results['employees'] = 'PASS'
else:
    results['employees'] = f"FAIL {r.status_code} {r.text}"
print(r.status_code, len(r.json().get('items', [])) if r.status_code == 200 else r.text)

# 4) GET /api/v1/clients
print("\n[4] GET /api/v1/clients")
r = httpx.get(f"{BASE}/api/v1/clients", headers=headers, timeout=15)
if r.status_code == 200 and len(r.json().get('items', [])) >= 3:
    results['clients'] = 'PASS'
else:
    results['clients'] = f"FAIL {r.status_code} {r.text}"
print(r.status_code, len(r.json().get('items', [])) if r.status_code == 200 else r.text)

# 5) GET /api/v1/contracts
print("\n[5] GET /api/v1/contracts")
r = httpx.get(f"{BASE}/api/v1/contracts", headers=headers, timeout=15)
if r.status_code == 200:
    items = r.json().get('items', [])
    correct = True
    for c in items:
        if abs(float(c.get('total_value', 0)) - float(c.get('remaining_value', 0))) > 1e-6 and c.get('status') == 'active':
            # remaining must be <= total for active (invoiced may be 0 now)
            correct = False
    results['contracts'] = 'PASS' if len(items) >= 3 and correct else f"FAIL len={len(items)} correct={correct}"
else:
    results['contracts'] = f"FAIL {r.status_code} {r.text}"
print(r.status_code, r.text)

# 6) GET /api/v1/projects
print("\n[6] GET /api/v1/projects")
r = httpx.get(f"{BASE}/api/v1/projects", headers=headers, timeout=15)
if r.status_code == 200 and len(r.json().get('items', [])) >= 5:
    results['projects'] = 'PASS'
else:
    results['projects'] = f"FAIL {r.status_code} {r.text}"
print(r.status_code, len(r.json().get('items', [])) if r.status_code == 200 else r.text)

# 7) GET /api/v1/pay-rates
print("\n[7] GET /api/v1/pay-rates")
r = httpx.get(f"{BASE}/api/v1/pay-rates", headers=headers, timeout=15)
if r.status_code == 200:
    items = r.json().get('items', [])
    if len(items) >= 8 and all(float(x.get('hourly_cost', 0)) > 0 for x in items):
        results['pay_rates'] = 'PASS'
    else:
        results['pay_rates'] = f"FAIL count={len(items)}"
else:
    results['pay_rates'] = f"FAIL {r.status_code} {r.text}"
print(r.status_code, r.text)

# 8) Cost a timesheet for Ahmed
print("\n[8] POST /api/v1/timesheets/cost")
employees = r = httpx.get(f"{BASE}/api/v1/employees", headers=headers, timeout=15).json().get('items', [])

ahmed = next((e for e in employees if e.get('full_name_en') == 'Ahmed Al-Zahrani'), None)
if not ahmed:
    results['timesheet_cost'] = 'FAIL Ahmed missing'
    print('Ahmed not found')
else:
    # find timesheet for Ahmed
    ts_list = httpx.get(f"{BASE}/api/v1/timesheets", params={'employee_id': ahmed['id']}, timeout=15).json().get('items', [])
    if not ts_list:
        results['timesheet_cost'] = 'FAIL no timesheet'
    else:
        ts = ts_list[0]
        pay_res = httpx.post(f"{BASE}/api/v1/timesheets/cost", json={
            'timesheet_id': ts['id'],
            'employee_id': ahmed['id'],
            'work_date': '2026-03-02',
            'hours': 8,
        }, headers=headers, timeout=15)
        if pay_res.status_code == 201:
            results['timesheet_cost'] = 'PASS'
        else:
            results['timesheet_cost'] = f"FAIL {pay_res.status_code} {pay_res.text}"
        print(pay_res.status_code, pay_res.text)

# 9) POST /api/v1/expenses
print("\n[9] POST /api/v1/expenses")
projects = httpx.get(f"{BASE}/api/v1/projects", headers=headers, timeout=15).json().get('items', [])
project_aramco = next((p for p in projects if p.get('project_number') == 'PRJ-2026-001'), None)
if not project_aramco:
    results['expenses'] = 'FAIL no project'
else:
    expense_res = httpx.post(f"{BASE}/api/v1/expenses", json={
        'project_id': project_aramco['id'],
        'expense_date': '2026-03-05',
        'category': 'subcontractor',
        'description': 'Test subcontractor cost',
        'amount_net': 1000.00,
        'vat_amount': 150.00,
    }, headers=headers, timeout=15)
    if expense_res.status_code == 201:
        results['expenses'] = 'PASS'
    else:
        results['expenses'] = f"FAIL {expense_res.status_code} {expense_res.text}"
    print(expense_res.status_code, expense_res.text)

# 10) POST /api/v1/invoices
print("\n[10] POST /api/v1/invoices")
contract_aramco = next((c for c in httpx.get(f"{BASE}/api/v1/contracts", headers=headers, timeout=15).json().get('items', []) if c.get('po_number') == 'PO-ARAMCO-2026-001'), None)
if not contract_aramco or not project_aramco:
    results['invoices'] = 'FAIL no contract/project'
else:
    inv_res = httpx.post(f"{BASE}/api/v1/invoices", json={
        'project_id': project_aramco['id'],
        'po_id': contract_aramco['id'],
        'client_name': 'Saudi Aramco',
        'invoice_date': '2026-03-28',
        'due_date': '2026-04-15',
        'subtotal_sar': 50000.00,
        'vat_rate': 0.15,
        'description': 'March 2026 billing for Aramco HSE',
    }, headers=headers, timeout=15)
    if inv_res.status_code == 201:
        inv_id = inv_res.json().get('id')
        results['invoices'] = 'PASS'
    else:
        results['invoices'] = f"FAIL {inv_res.status_code} {inv_res.text}"
        inv_id = None
    print(inv_res.status_code, inv_res.text)

# 11) POST /api/v1/invoices/{id}/gl-post
print("\n[11] POST /api/v1/invoices/{id}/gl-post")
if inv_id:
    glres = httpx.post(f"{BASE}/api/v1/invoices/{inv_id}/gl-post", headers=headers, timeout=15)
    if glres.status_code == 200:
        results['invoice_gl_post'] = 'PASS'
    else:
        results['invoice_gl_post'] = f"FAIL {glres.status_code} {glres.text}"
    print(glres.status_code, glres.text)
else:
    results['invoice_gl_post'] = 'SKIP no invoice id'

# 12) GET /api/v1/dashboard
print("\n[12] GET /api/v1/dashboard")
db_res = httpx.get(f"{BASE}/api/v1/dashboard", headers=headers, params={'start': '2026-03-01', 'end': '2026-03-31'}, timeout=15)
if db_res.status_code == 200 and 'revenue_net' in db_res.json():
    results['dashboard'] = 'PASS'
else:
    results['dashboard'] = f"FAIL {db_res.status_code} {db_res.text}"
print(db_res.status_code, db_res.text)

# 13) RBAC: employee cannot create client
print("\n[13] RBAC employee should not create client")
emp_email = 'employee_test@sarc.sa'
# Try signup (may exist)
signup_res = httpx.post(f"{BASE}/auth/signup", json={
    'tenant_id': TENANT_ID,
    'email': emp_email,
    'password': 'Emp@2025!',
    'full_name': 'Employee Test',
    'user_type': 'employee',
}, timeout=15)

if signup_res.status_code not in (201, 409):
    print('Unexpected signup', signup_res.status_code, signup_res.text)

login_res = httpx.post(f"{BASE}/auth/login", json={
    'tenant_id': TENANT_ID,
    'email': emp_email,
    'password': 'Emp@2025!',
}, timeout=15)

if login_res.status_code != 200:
    results['rbac'] = f"FAIL login {login_res.status_code} {login_res.text}"
    print(login_res.status_code, login_res.text)
else:
    emp_token = login_res.json().get('access_token')
    emp_headers = {'Authorization': f'Bearer {emp_token}'}
    post_client = httpx.post(f"{BASE}/api/v1/clients", json={
        'name_en': 'RBAC Test Client',
        'city': 'Riyadh',
        'country': 'SA'
    }, headers=emp_headers, timeout=15)
    if post_client.status_code in (403, 401):
        results['rbac'] = 'PASS'
    else:
        results['rbac'] = f"FAIL {post_client.status_code} {post_client.text}"
    print(post_client.status_code, post_client.text)

# Summary
print("\n=== TEST SUMMARY ===")
for k, v in results.items():
    print(f"{k}: {v}")

print("=== Test Full Flow End ===")

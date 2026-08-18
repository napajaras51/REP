# NHSO REP Web Application — Master Implementation Guide for Codex

> **Project:** NHSO REP Download Manager  
> **Purpose:** แปลงระบบดาวน์โหลด REP จาก NHSO e-Claim ที่ปัจจุบันใช้งานผ่าน Python + PowerShell/CLI ให้เป็น Local Web Application บน Windows โดยยังคง Download Engine, NHSO OSS/SSO, Windows DPAPI, Playwright และพฤติกรรมเดิมไว้  
> **Primary platform:** Windows 10/11  
> **Primary language:** Python 3.10+  
> **Web backend:** FastAPI  
> **Frontend:** HTML + Bootstrap 5 + Vanilla JavaScript  
> **Initial database:** SQLite  
> **Existing core script:** `nhso_rep_paginated_download.py`  
> **Important principle:** Refactor incrementally. Do not rewrite the working NHSO integration from scratch.

---

# 1. บทนำและเป้าหมายของโครงการ

ปัจจุบันระบบมี Python script สำหรับดาวน์โหลดไฟล์ REP จาก NHSO e-Claim โดยผู้ใช้ต้องเปิด PowerShell และระบุ command-line arguments เช่น:

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --insecure
```

ระบบเดิมรองรับตัวเลือกหลักอยู่แล้ว ได้แก่:

- `--start`
- `--end`
- `--path`
- `--hcode`
- `--page-size`
- `--overwrite`
- `--dry-run`
- `--insecure`
- `--sso-login`
- `--legacy-login`
- `--config`

เป้าหมายของโครงการคือสร้าง Web Application เพื่อให้ผู้ใช้ทั่วไปไม่ต้องพิมพ์ PowerShell แต่สามารถ:

1. เปิด Browser
2. เลือกช่วงวันที่
3. เลือกหรือกำหนดโฟลเดอร์ปลายทาง
4. เลือก Dry Run / Overwrite
5. ตรวจสอบสถานะ NHSO SSO
6. Login NHSO เมื่อ session หมดอายุ
7. ตรวจรายการ REP ก่อนดาวน์โหลด
8. กดเริ่มดาวน์โหลด
9. ดู progress และ log
10. ดูสรุปผล
11. ดูประวัติการทำงานย้อนหลัง

Web UI เป็นเพียงชั้นควบคุมเหนือ Python Download Engine เดิม ไม่ใช่การเขียนระบบ NHSO integration ใหม่ทั้งหมด

---

# 2. เป้าหมายเชิงสถาปัตยกรรม

โครงสร้างเป้าหมาย:

```text
User
  │
  ▼
Browser
http://127.0.0.1:8000
  │
  ▼
Frontend
HTML + Bootstrap + JavaScript
  │
  ▼
FastAPI
  │
  ├── Download API
  ├── Auth / SSO API
  ├── Job Status API
  ├── Settings API
  └── History API
  │
  ▼
REP Service Layer
  │
  ├── NHSO Authentication
  ├── Search / Pagination
  ├── Date Filtering
  ├── File Download
  ├── Retry
  └── Statistics
  │
  ├──────────────► Windows DPAPI
  │
  ├──────────────► Playwright / Chrome
  │
  ├──────────────► NHSO e-Claim
  │
  └──────────────► Local Download Folder
```

หลักการสำคัญ:

```text
CLI ─────┐
         ├──► download_rep(...)
Web App ─┘
```

ทั้ง CLI และ Web App ต้องเรียก Download Engine เดียวกัน

---

# 3. สิ่งที่มีอยู่ในระบบเดิมและต้องรักษา

Codex ต้องอ่าน `nhso_rep_paginated_download.py` ฉบับปัจจุบันทั้งหมดก่อนแก้ไข

ระบบเดิมมีความสามารถสำคัญดังนี้:

## 3.1 NHSO endpoints

มี constants สำหรับ:

- Authentication
- Authentication information
- Token refresh
- Search upload records
- REP download
- NHSO Client URL

ห้ามเปลี่ยน endpoints โดยไม่มีเหตุผลและหลักฐานว่าระบบเดิมใช้งานไม่ได้

---

## 3.2 Windows DPAPI

ระบบเดิมใช้:

```python
CryptProtectData
CryptUnprotectData
```

เพื่อเข้ารหัส NHSO SSO token

Token ถูกเก็บใน:

```text
%APPDATA%\AutoRepNHSO\sso_token.dat
```

ข้อบังคับ:

- ห้ามเปลี่ยนเป็น plain text
- ห้ามเก็บ token ใน SQLite
- ห้ามส่ง token ไป frontend
- ห้ามแสดง token ใน log
- ห้าม expose token ผ่าน API
- ห้าม copy token ระหว่าง Windows users
- ต้องรักษา DPAPI behavior เดิมไว้

---

## 3.3 NHSO OSS/SSO Browser Login

ระบบเดิมใช้ Playwright และ persistent Chrome profile

หลักการปัจจุบัน:

```text
Open Chrome
   ↓
User Login NHSO OSS
   ↓
Return to NHSO e-Claim Client
   ↓
Read localStorage token
   ↓
Encrypt with DPAPI
   ↓
Save token
```

ต้องรักษา workflow นี้

Web App สามารถมีปุ่ม:

```text
[ Login NHSO ]
```

เมื่อกดแล้ว backend จึงเรียก:

```python
browser_sso_login(...)
```

อย่าพยายามฝังหน้า login ของ NHSO ไว้ใน iframe

---

## 3.4 Token Refresh

เมื่อมี saved token ระบบเดิมพยายาม refresh ก่อนใช้งาน

ห้ามตัดขั้นตอนนี้ทิ้ง

สถานะที่ Web App ควรแสดง:

```text
SSO Status

● Ready
● Login required
● Session expired
● Checking...
```

Frontend ไม่จำเป็นต้องรู้ token จริง

---

## 3.5 Pagination

ระบบเดิมค้นหารายการ REP แบบ pagination

แนวคิด:

```python
page = 0

while True:
    items, meta = search_page(...)

    ...

    if len(items) < page_size:
        break

    page += 1
```

ต้องรักษา behavior เดิม

Default:

```text
page_size = 3000
```

หน้า Web App ไม่จำเป็นต้องให้ผู้ใช้ทั่วไปแก้ค่า page size ใน Phase 1

สามารถซ่อนไว้ใน Advanced Settings

---

## 3.6 Date filtering

ระบบเดิมแปลงวันที่ Gregorian เป็น token ปี พ.ศ. เพื่อ match กับ filename

ตัวอย่าง:

```text
2026-05-01
→
25690501
```

ห้ามเปลี่ยน logic นี้โดยไม่ทดสอบกับ filename จริง

Web UI ใช้วันที่แบบ `YYYY-MM-DD` ภายใน

หน้าแสดงผลภาษาไทยสามารถแสดง พ.ศ. ได้ แต่ API/backend ให้ใช้ ISO date

---

## 3.7 Ready status

ระบบเดิมถือว่ารายการพร้อมเมื่อ:

```python
loaded == "Y"
```

หรือ

```python
dataStatus == "1"
```

ต้องรักษา behavior นี้

---

## 3.8 File naming

ระบบเดิมแปลง:

```text
*.ecd
```

เป็น:

```text
*_REP.xls
```

ผ่าน `output_name()`

ห้ามเปลี่ยนชื่อไฟล์โดยพลการ

---

## 3.9 Existing-file handling

ถ้าไฟล์มีอยู่แล้ว:

```text
overwrite = false
```

ต้อง skip

ผลลัพธ์:

```text
exists
```

ถ้า:

```text
overwrite = true
```

จึงอนุญาตให้เขียนทับ

ค่า default ใน Web App ต้องเป็น:

```text
Overwrite = OFF
```

---

## 3.10 Retry

ระบบเดิม retry download เมื่อเกิด network error หรือ HTTP status เช่น:

```text
429
500
502
503
504
```

และมี delay ตามลำดับ

ต้องรักษา retry behavior

ห้ามให้ Web App ตัด retry เดิมทิ้ง

---

## 3.11 Temporary `.part` file

ระบบเดิมเขียน:

```text
filename.xls.part
```

ก่อนแล้วจึง replace เป็นไฟล์จริง

ต้องรักษา behavior นี้เพื่อป้องกันไฟล์เสียหายจาก download ไม่ครบ

---

# 4. Non-negotiable rules สำหรับ Codex

Codex ต้องปฏิบัติตามข้อกำหนดเหล่านี้ทุก Phase

## 4.1 ห้าม Rewrite Integration จากศูนย์

ห้ามเขียน NHSO integration ใหม่ทั้งหมดหากไม่จำเป็น

ให้ refactor ของเดิม

---

## 4.2 ห้ามทำ CLI เดิมพัง

หลัง Phase 1 ต้องยังใช้งานคำสั่งเดิมได้ เช่น:

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --dry-run --insecure
```

---

## 4.3 Backup ก่อนแก้ไฟล์ core

ก่อน refactor:

```text
nhso_rep_paginated_download.py
```

สร้าง backup เช่น:

```text
backup/
nhso_rep_paginated_download_before_webapp_YYYYMMDD_HHMMSS.py
```

หรือใช้ Git commit ก่อนแก้

---

## 4.4 ห้ามส่ง user input เข้า shell command โดยตรง

ห้ามใช้แนวทางนี้:

```python
os.system(...)
subprocess.run("python script.py " + user_input, shell=True)
```

สำหรับการทำงานหลัก

Web API ต้องเรียก Python function โดยตรง

---

## 4.5 ห้ามใช้ `shell=True` กับข้อมูลจาก Web UI

โดยเฉพาะ:

- path
- date
- hcode
- filename
- config

---

## 4.6 ห้าม expose credentials

ห้าม:

- return token ผ่าน API
- log token
- log password
- แสดง DPAPI bytes
- เก็บ NHSO token ลง browser localStorage ของ Web App
- เก็บ password ใน frontend

---

## 4.7 ห้ามให้ Web App เปิดรับ network ภายนอกเป็นค่า default

Phase 1 ต้อง bind:

```text
127.0.0.1
```

ไม่ใช่:

```text
0.0.0.0
```

จนกว่าจะมี authentication และ security review

---

## 4.8 ห้ามลบ source file หรือไฟล์ REP เดิม

Web App ไม่มีฟังก์ชัน delete REP ใน Phase 1–2

---

## 4.9 Dry Run ต้องไม่ดาวน์โหลดไฟล์

Dry Run ต้อง:

- search
- filter
- list matched files
- calculate stats

แต่ห้ามเขียน REP file จริง

---

## 4.10 Overwrite default = false

ผู้ใช้ต้องเลือกเองหากต้องการ overwrite

---

# 5. Development Strategy

พัฒนาเป็น Phase ตามลำดับ

```text
Phase 0  Baseline / Safety
Phase 1  Refactor Core Engine
Phase 2  CLI Regression Test
Phase 3  FastAPI Foundation
Phase 4  Web UI MVP
Phase 5  Job Manager + Progress
Phase 6  SQLite History
Phase 7  Settings + Presets
Phase 8  UX / Validation / Error Handling
Phase 9  Packaging for Windows
Phase 10 Optional Automation / Integration
```

ห้ามกระโดดไปสร้าง UI ใหญ่ก่อน Core Engine เสถียร

---

# 6. Phase 0 — Baseline และ Safety

## Goal

ยืนยันว่า script เดิมทำงานก่อน refactor

## Tasks

1. ตรวจ Git status
2. ถ้ายังไม่มี Git repository ให้พิจารณา initialize
3. backup core script
4. ตรวจ Python version
5. ตรวจ dependencies
6. ตรวจว่า script import ได้
7. บันทึกตัวอย่าง command ที่ใช้งานจริง
8. รัน dry-run baseline
9. จด output stats

## Suggested commands

```powershell
python --version
python -m pip list
python -m py_compile .\nhso_rep_paginated_download.py
```

Dry run ตัวอย่าง:

```powershell
python .\nhso_rep_paginated_download.py `
  --start 2026-05-01 `
  --end 2026-05-31 `
  --path "D:\REP\69\6906" `
  --dry-run `
  --insecure
```

## Acceptance criteria

- ไม่มี syntax error
- SSO เดิมยังทำงาน
- NHSO search ทำงาน
- dry run แสดง matched files
- ไม่มีไฟล์ถูกดาวน์โหลดใน dry run
- เก็บ baseline stats ไว้เปรียบเทียบ Phase 2

---

# 7. Phase 1 — Refactor Core Engine

## Goal

แยก business logic ออกจาก `main()`

ปัจจุบัน `main()` ทำหลายหน้าที่พร้อมกัน:

```text
Parse CLI
Load settings
Validate inputs
Authenticate
Refresh token
Resolve hcode
Search
Filter
Download
Build stats
Print result
```

ต้องแยกเป็น service function

---

# 8. Core Function ที่ต้องสร้าง

สร้าง function หลัก:

```python
def download_rep(
    start,
    end=None,
    dest_path=None,
    hcode=None,
    page_size=3000,
    overwrite=False,
    dry_run=False,
    insecure=False,
    sso_login=False,
    legacy_login=False,
    config=None,
    progress_callback=None,
    log_callback=None,
):
    ...
```

หมายเหตุ:

`progress_callback` และ `log_callback` สามารถเพิ่มใน Phase 1 เลยหรือ Phase 5 ก็ได้

แต่ design ต้องรองรับ Web App

---

# 9. Input contract ของ `download_rep`

## start

Type:

```python
str
```

Format:

```text
YYYY-MM-DD
```

Required

---

## end

Type:

```python
str | None
```

Format:

```text
YYYY-MM-DD
```

ถ้า None:

ใช้ saved setting หรือ today ตาม behavior ที่เหมาะสมกับระบบเดิม

ต้องกำหนด behavior ให้ชัดเจนและเขียน test

---

## dest_path

Type:

```python
str | Path | None
```

Fallback:

```text
settings.path
```

จากนั้น:

```text
C:\TEMP\REP
```

---

## overwrite

Boolean

Default:

```text
false
```

---

## dry_run

Boolean

Default:

```text
false
```

---

## insecure

Boolean

รักษา behavior เดิม

แต่ Web UI ต้องแสดง warning หากเปิด

---

## sso_login

Boolean

ถ้า true:

เปิด Chrome ให้ user login

---

# 10. Validation

สร้าง validation function แยก:

```python
def validate_download_request(...):
    ...
```

ตรวจ:

1. start format
2. end format
3. start <= end
4. date range ไม่ผิดปกติ
5. path ไม่ว่าง
6. path สร้างได้
7. page_size > 0
8. hcode ถ้าระบุ ต้องเป็นรูปแบบที่ยอมรับได้
9. legacy login ต้องมี username/password

อย่า trust input จาก browser

---

# 11. Result contract

`download_rep()` ต้อง return structured object/dict

แนะนำ:

```python
{
    "success": True,
    "status": "completed",
    "hcode": "11066",
    "start_date": "2026-05-01",
    "end_date": "2026-05-31",
    "destination": r"D:\REP\69\6906",
    "dry_run": False,
    "overwrite": False,

    "stats": {
        "pages": 2,
        "seen": 3120,
        "matched": 26,
        "date_skipped": 3090,
        "status_skipped": 4,
        "exists": 8,
        "downloaded": 18,
        "failed": 0
    },

    "files": [
        {
            "source_name": "...ecd",
            "output_name": "..._REP.xls",
            "result": "downloaded"
        }
    ],

    "warnings": [],
    "errors": []
}
```

เหตุผล:

Web App ต้องแสดงผลโดยไม่ parse stdout

---

# 12. Stats ที่ต้องเพิ่ม

ระบบเดิมมี:

```text
pages
seen
date_skipped
status_skipped
exists
downloaded
failed
```

ควรเพิ่ม:

```text
matched
```

Definition:

```text
matched = ผ่าน date filter และ ready filter
```

Dry run ต้องเห็น:

```text
matched > 0
downloaded = 0
```

---

# 13. Exception strategy

ห้ามใช้ `SystemExit` ภายใน service layer

Service layer ควรใช้ exception เช่น:

```python
ValueError
RuntimeError
requests.RequestException
```

`SystemExit` ใช้ได้เฉพาะ CLI boundary

ตัวอย่าง:

```python
try:
    result = download_rep(...)
except ValueError as exc:
    ...
```

FastAPI จึงสามารถ map exception เป็น HTTP response ได้

---

# 14. Logging strategy

อย่าใช้ `print()` เป็นกลไกเดียว

สร้าง logger:

```python
import logging

logger = logging.getLogger(__name__)
```

ใช้ levels:

```text
DEBUG
INFO
WARNING
ERROR
```

ตัวอย่าง:

```python
logger.info("Searching NHSO REP page %s", page)
logger.warning("Download retry: %s", filename)
logger.error("Download failed: %s", filename)
```

ห้าม log:

```text
token
password
Authorization header
```

CLI สามารถยังเห็นข้อความผ่าน logging handler

Web App สามารถ capture ผ่าน callbacks หรือ job log store

---

# 15. Suggested module structure หลัง Refactor

ไม่จำเป็นต้องแยกทั้งหมดใน commit แรก

เป้าหมายระยะกลาง:

```text
nhso_rep_webapp/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── downloads.py
│   │   ├── auth.py
│   │   ├── jobs.py
│   │   ├── history.py
│   │   └── settings.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rep_service.py
│   │   ├── nhso_auth.py
│   │   ├── nhso_client.py
│   │   ├── token_store.py
│   │   └── job_service.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py
│   │   └── database.py
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── history.html
│   │   └── settings.html
│   │
│   └── static/
│       ├── css/
│       │   └── app.css
│       └── js/
│           └── app.js
│
├── data/
│   └── app.db
│
├── logs/
│
├── tests/
│   ├── test_dates.py
│   ├── test_validation.py
│   ├── test_output_name.py
│   ├── test_service.py
│   └── test_api.py
│
├── backup/
│
├── nhso_rep_paginated_download.py
├── run_webapp.py
├── requirements.txt
├── README_TH.md
└── .gitignore
```

Codex สามารถปรับ structure ให้เหมาะสมได้ แต่ต้องอธิบายเหตุผล

---

# 16. Phase 2 — Preserve CLI

หลัง `download_rep()` พร้อม

แก้ `main()` ให้ทำหน้าที่เฉพาะ:

```text
CLI parsing
     ↓
download_rep(...)
     ↓
format output
```

Pseudo-code:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()

    result = download_rep(
        start=args.start,
        end=args.end,
        dest_path=args.path,
        hcode=args.hcode,
        page_size=args.page_size,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        insecure=args.insecure,
        sso_login=args.sso_login,
        legacy_login=args.legacy_login,
        config=args.config,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )
```

---

# 17. CLI Regression Tests

ทดสอบอย่างน้อย:

## Test A — Dry run

```powershell
python .\nhso_rep_paginated_download.py `
 --start 2026-05-01 `
 --end 2026-05-31 `
 --path "D:\REP\69\6906" `
 --dry-run `
 --insecure
```

ต้อง:

- search ได้
- matched count ถูกต้อง
- ไม่ download

---

## Test B — Existing file

รัน download ซ้ำโดยไม่ overwrite

ต้องได้:

```text
exists > 0
```

และไม่แก้ไฟล์เดิม

---

## Test C — Overwrite

ทดสอบเฉพาะเมื่อผู้ดูแลอนุญาต

---

## Test D — Missing SSO

กรณีไม่มี token:

ต้อง error ชัดเจน

ไม่ crash แบบ traceback ที่ user อ่านไม่รู้เรื่อง

---

## Test E — Expired SSO

ต้องแจ้ง:

```text
NHSO session expired. Login again.
```

---

# 18. Phase 3 — FastAPI Foundation

ติดตั้ง:

```powershell
python -m pip install fastapi uvicorn jinja2 python-multipart
```

เพิ่ม requirements

แนะนำ:

```text
fastapi
uvicorn[standard]
jinja2
python-multipart
requests
urllib3
playwright
```

pin versions เมื่อระบบเริ่ม stable

---

# 19. FastAPI Application

ตัวอย่าง:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="NHSO REP Download Manager",
    version="1.0.0",
)
```

Phase 1 bind เฉพาะ localhost

Run:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

# 20. API Design

## GET `/api/health`

Response:

```json
{
  "status": "ok"
}
```

---

## GET `/api/auth/status`

Purpose:

ตรวจว่า saved SSO token มีหรือไม่

หากเป็นไปได้ตรวจ refresh/auth-info

Response:

```json
{
  "status": "ready",
  "logged_in": true,
  "hcode": "11066"
}
```

หรือ:

```json
{
  "status": "login_required",
  "logged_in": false
}
```

ห้าม return token

---

## POST `/api/auth/login`

Purpose:

เปิด Chrome เพื่อ NHSO login

Important:

Playwright login เป็น blocking operation

Phase แรกสามารถทำ synchronous ได้ชั่วคราว แต่ควรย้ายเป็น job ภายหลัง

Response เมื่อสำเร็จ:

```json
{
  "success": true,
  "status": "ready"
}
```

---

## POST `/api/downloads/preview`

เทียบเท่า Dry Run

Request:

```json
{
  "start_date": "2026-05-01",
  "end_date": "2026-05-31",
  "destination": "D:\\REP\\69\\6906"
}
```

Backend:

```python
download_rep(
    ...,
    dry_run=True
)
```

Response:

```json
{
  "success": true,
  "stats": {
    "matched": 26
  },
  "files": [...]
}
```

---

## POST `/api/downloads`

เริ่ม actual download

Request:

```json
{
  "start_date": "2026-05-01",
  "end_date": "2026-05-31",
  "destination": "D:\\REP\\69\\6906",
  "overwrite": false
}
```

ระยะยาวควร return:

```json
{
  "job_id": "..."
}
```

ไม่ควร block HTTP request จนดาวน์โหลดทั้งหมดเสร็จ

---

## GET `/api/jobs/{job_id}`

ตัวอย่าง:

```json
{
  "job_id": "abc123",
  "status": "running",
  "progress": {
    "pages": 1,
    "seen": 3000,
    "matched": 18,
    "downloaded": 12,
    "exists": 4,
    "failed": 0
  }
}
```

---

## GET `/api/jobs/{job_id}/logs`

Return log ล่าสุด

---

## GET `/api/history`

ประวัติงาน

---

# 21. Pydantic Schemas

สร้าง schema เช่น:

```python
class DownloadRequest(BaseModel):
    start_date: date
    end_date: date
    destination: str
    overwrite: bool = False
    dry_run: bool = False
```

Validation:

```python
if end_date < start_date:
    raise ValueError(...)
```

อย่ารับ arbitrary dictionary แล้วใช้โดยไม่ validate

---

# 22. Phase 4 — Web UI MVP

หน้าแรก:

```text
┌─────────────────────────────────────────────────────┐
│ NHSO REP Download Manager                           │
│ โรงพยาบาล                                           │
├─────────────────────────────────────────────────────┤
│ NHSO SSO                                            │
│ ● พร้อมใช้งาน                                       │
│ [เข้าสู่ระบบ NHSO ใหม่]                             │
├─────────────────────────────────────────────────────┤
│ ช่วงข้อมูล                                           │
│                                                     │
│ วันที่เริ่มต้น     [ 2026-05-01 ]                    │
│ วันที่สิ้นสุด      [ 2026-05-31 ]                    │
│                                                     │
│ โฟลเดอร์          [ D:\REP\69\6906 ]               │
│                                                     │
│ [ ] เขียนทับไฟล์เดิม                                │
│                                                     │
│ [ตรวจสอบรายการ]     [เริ่มดาวน์โหลด]                │
├─────────────────────────────────────────────────────┤
│ สถานะ                                               │
│ Found: 26                                           │
│ Downloaded: 18                                      │
│ Existing: 8                                         │
│ Failed: 0                                           │
└─────────────────────────────────────────────────────┘
```

---

# 23. UX Principle

ผู้ใช้ไม่ควรต้องรู้คำว่า:

```text
--start
--end
--path
--dry-run
--overwrite
```

Mapping:

```text
วันที่เริ่มต้น → start
วันที่สิ้นสุด → end
โฟลเดอร์ → dest_path
ตรวจสอบรายการ → dry_run=True
เขียนทับไฟล์ → overwrite=True
```

---

# 24. Form fields

## Start Date

HTML:

```html
<input type="date">
```

Required

---

## End Date

HTML date

Required

---

## Destination Folder

Browser security ไม่อนุญาตให้ web page เลือก arbitrary local folder path แบบ native ได้ง่ายเหมือน desktop app

สำหรับ Local Web App Phase 1 ให้ใช้วิธีหนึ่ง:

### Option A — text input

```text
D:\REP\69\6906
```

ง่ายที่สุด

### Option B — backend native folder dialog

สร้าง API ที่ backend เรียก Windows folder picker เช่น tkinter

เหมาะกับ localhost app

แต่ต้องระวัง threading/UI interaction

แนะนำทำหลัง MVP

---

# 25. Date Presets

เพิ่ม preset:

```text
○ เดือนนี้
○ เดือนที่แล้ว
○ ปีงบประมาณปัจจุบัน
○ กำหนดเอง
```

Backend หรือ frontend คำนวณ date range

สำหรับ fiscal year ไทย:

```text
1 ตุลาคม
ถึง
30 กันยายน
```

ต้องเขียน utility function พร้อม unit tests

---

# 26. Month Picker

สามารถเพิ่ม:

```text
ปีงบประมาณ [2569]
เดือน       [พฤษภาคม]
```

ระบบคำนวณ:

```text
start = first day
end   = last day
```

ใช้ calendar library

อย่า hard-code จำนวนวันของเดือน

---

# 27. Multi-month selection — Phase หลัง

UI:

```text
ปีงบประมาณ 2569

[x] ตุลาคม 2568
[x] พฤศจิกายน 2568
[x] ธันวาคม 2568
[x] มกราคม 2569
...
```

มี 2 design:

### A. One job ต่อ date range รวม

### B. One child job ต่อเดือน

แนะนำ B หากต้องการ tracking และ retry แยกเดือนในอนาคต

Phase แรกไม่จำเป็น

---

# 28. Phase 5 — Job Manager

Download อาจใช้เวลานาน

ห้ามทำงานทั้งหมดใน request thread ระยะยาว

สร้าง Job abstraction

```python
class DownloadJob:
    id
    status
    created_at
    started_at
    completed_at
    request
    stats
    error
```

Status:

```text
queued
running
completed
completed_with_errors
failed
cancelled
```

Phase แรกสามารถใช้:

```python
ThreadPoolExecutor(max_workers=1)
```

เพราะ local app และไม่ควรให้หลาย download jobs ยิง NHSO พร้อมกัน

---

# 29. Concurrency rule

Default:

```text
1 active download job
```

ถ้ามี job กำลัง running แล้ว user กด download อีกครั้ง:

Response:

```text
มีงานดาวน์โหลดกำลังทำงานอยู่
```

หรือ queue

อย่ารัน parallel หลาย job โดย default

---

# 30. Progress callback

ปรับ `download_rep()` ให้รองรับ:

```python
def download_rep(..., progress_callback=None):
```

ส่ง event:

```python
progress_callback({
    "event": "page_loaded",
    "page": page,
    "seen": stats["seen"],
})
```

และ:

```python
progress_callback({
    "event": "file_result",
    "filename": dest_name,
    "result": result,
    "stats": stats.copy(),
})
```

---

# 31. Log callback

รองรับ:

```python
log_callback(message, level="info")
```

เพื่อ Web UI แสดง:

```text
12:30:01 Searching page 0...
12:30:03 Found 3000 records
12:30:04 Match: ...
12:30:05 downloaded: ...
```

ห้ามมี token

---

# 32. Frontend polling

Phase แรกง่ายที่สุด:

```text
POST /api/downloads
→ job_id

ทุก 1 วินาที:
GET /api/jobs/{id}
```

ไม่จำเป็นต้องใช้ WebSocket ตั้งแต่แรก

---

# 33. Progress Bar

UI:

```text
กำลังดาวน์โหลด

██████████████░░░░░  72%

พบ          26
ดาวน์โหลด   18
มีอยู่แล้ว    6
ผิดพลาด      0
```

ข้อควรระวัง:

NHSO `totalSize` อาจเป็นจำนวน records ก่อน date filter

ดังนั้นเปอร์เซ็นต์แบบ precise อาจไม่รู้ตั้งแต่แรก

ให้ใช้:

- indeterminate progress ระหว่าง search
- file progress หลังรู้ matched files

หรือแสดง counts แทน

---

# 34. Phase 6 — SQLite History

ใช้ SQLite สำหรับ metadata เท่านั้น

ห้ามเก็บ:

- NHSO token
- password
- REP file content

---

# 35. Database schema

## Table: `download_jobs`

```sql
CREATE TABLE download_jobs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,

    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    destination TEXT NOT NULL,

    hcode TEXT,
    dry_run INTEGER NOT NULL DEFAULT 0,
    overwrite INTEGER NOT NULL DEFAULT 0,

    status TEXT NOT NULL,

    pages INTEGER NOT NULL DEFAULT 0,
    seen INTEGER NOT NULL DEFAULT 0,
    matched INTEGER NOT NULL DEFAULT 0,
    date_skipped INTEGER NOT NULL DEFAULT 0,
    status_skipped INTEGER NOT NULL DEFAULT 0,
    exists_count INTEGER NOT NULL DEFAULT 0,
    downloaded INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,

    error_message TEXT
);
```

---

## Table: `download_files`

```sql
CREATE TABLE download_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,

    source_name TEXT,
    output_name TEXT,
    result TEXT,

    created_at TEXT NOT NULL,

    FOREIGN KEY(job_id)
        REFERENCES download_jobs(id)
);
```

---

# 36. History Page

แสดง:

| วันที่ | ช่วงข้อมูล | พบ | Downloaded | Existing | Failed | สถานะ |
|---|---|---:|---:|---:|---:|---|

คลิก job ดูรายละเอียดได้

---

# 37. Job Detail

แสดง:

```text
Job ID
วันที่เริ่มงาน
ช่วง REP
Folder
Status

Seen
Matched
Downloaded
Existing
Failed

File results
Logs
```

---

# 38. Phase 7 — Settings

Settings ที่เก็บได้:

```text
default_destination
default_page_size
default_insecure
last_start_date
last_end_date
```

อย่าเก็บ token

---

# 39. Settings storage

สามารถใช้:

```text
%APPDATA%\AutoRepNHSO\webapp_settings.json
```

หรือ SQLite

เนื่องจากมี `settings.dat` เดิมอยู่แล้ว:

Codex ต้องระวังไม่ทำ format เดิมพัง

ทางเลือกปลอดภัย:

```text
settings.dat          ← legacy
webapp_settings.json  ← web app
sso_token.dat         ← DPAPI token
```

---

# 40. Default destination

อนุญาตให้ผู้ใช้ตั้ง:

```text
D:\REP
```

และเลือก auto folder pattern ภายหลัง:

```text
D:\REP\69\6906
```

อย่า implement pattern ซับซ้อนก่อนยืนยันความต้องการ

---

# 41. Phase 8 — Error Handling

แยก error types

## Validation Error

เช่น:

```text
วันที่เริ่มต้นต้องไม่มากกว่าวันที่สิ้นสุด
```

HTTP:

```text
400
```

---

## Authentication Error

```text
ไม่พบ NHSO SSO session
```

หรือ:

```text
NHSO session หมดอายุ
```

UI ต้องแสดงปุ่ม:

```text
[ Login NHSO ]
```

---

## Network Error

แสดง:

```text
ไม่สามารถเชื่อมต่อ NHSO ได้หลังจาก retry
```

แต่ไม่ expose stack trace ต่อ user

---

## Permission Error

เช่น path เขียนไม่ได้

แสดง:

```text
ไม่มีสิทธิ์เขียนไฟล์ลงโฟลเดอร์นี้
```

---

## Disk Error

ถ้า disk full:

ต้อง fail อย่างชัดเจน

---

# 42. Error response format

แนะนำ:

```json
{
  "success": false,
  "error": {
    "code": "SSO_EXPIRED",
    "message": "NHSO session หมดอายุ กรุณาเข้าสู่ระบบใหม่"
  }
}
```

---

# 43. Security Requirements

ระบบนี้เชื่อม NHSO และข้อมูลโรงพยาบาล

ดังนั้นต้องมี security discipline

## Required

- localhost only by default
- DPAPI token
- no token logging
- no credential logging
- no shell=True
- validate paths
- CSRF consideration หากเพิ่ม state-changing HTML forms
- escape filenames ใน HTML
- sanitize error output
- dependency updates
- no hardcoded credentials

---

# 44. Path validation

Windows paths ต้องรองรับ:

```text
C:\TEMP\REP
D:\REP\69\6906
\\server\share\REP
```

สำหรับ UNC path:

Phase 1 อาจ support ได้ถ้า Windows user มี permission

ต้องไม่แก้ credential/share mapping อัตโนมัติ

---

# 45. Path traversal

แม้เป็น local app ให้ validate destination

อย่า concatenate path กับ arbitrary filename โดยไม่ใช้:

```python
Path(...)
```

สำหรับ NHSO filename:

ตรวจว่าไม่ประกอบด้วย path traversal เช่น:

```text
../
..\
```

สร้าง safe filename helper หากจำเป็น

---

# 46. File integrity

ระบบเดิมตรวจ:

```text
HTML
password
```

ใน response ต้นไฟล์เพื่อจับ session redirect/error

รักษาไว้

สามารถเพิ่มภายหลัง:

- minimum file size
- expected content type
- XLS signature validation

แต่ห้ามทำให้ไฟล์ legit ถูก reject โดยไม่ทดสอบ

---

# 47. Phase 9 — Windows Launcher

ผู้ใช้ไม่ควรเปิด PowerShell ใน final UX

สร้าง:

```text
Start NHSO REP Web App.bat
```

หรือ `.cmd`

ตัวอย่าง:

```bat
@echo off
cd /d "%~dp0"
python run_webapp.py
```

`run_webapp.py`:

1. start uvicorn on localhost
2. optionally open browser
3. show minimal console or hide later

---

# 48. Browser Auto-open

ใช้:

```python
webbrowser.open("http://127.0.0.1:8000")
```

หลัง server ready

ระวังเปิด browser ก่อน server start

---

# 49. Packaging options

หลังระบบ stable:

### Option A
Python installation required

ง่ายและ debug ง่าย

### Option B
PyInstaller

สร้าง executable

ต้องทดสอบ:

- Playwright
- Chrome
- DPAPI
- templates
- static files
- SQLite path
- APPDATA paths

อย่าทำ PyInstaller ก่อนระบบ Web App stable

---

# 50. Folder Picker

หากผู้ใช้ต้องการปุ่ม:

```text
[เลือกโฟลเดอร์]
```

Browser ไม่สามารถเลือก Windows absolute folder แล้วส่ง path แบบ native ได้โดยตรงในทุกกรณี

สำหรับ Local Web App สามารถสร้าง backend endpoint:

```text
POST /api/system/select-folder
```

backend ใช้ native Windows dialog

ตัวอย่าง conceptual:

```python
from tkinter import Tk, filedialog

root = Tk()
root.withdraw()

folder = filedialog.askdirectory()
```

ข้อควรระวัง:

- GUI main thread
- server thread
- multiple simultaneous dialogs

ทำหลัง MVP

---

# 51. SSO Status UX

Card:

```text
NHSO SSO

● พร้อมใช้งาน
รหัสหน่วยบริการ: 11066

[เข้าสู่ระบบใหม่]
```

เมื่อ session หมด:

```text
● ต้องเข้าสู่ระบบ

[Login NHSO]
```

ห้ามแสดง token expiry หากไม่ได้ข้อมูลจริง

---

# 52. Preview Flow

ผู้ใช้เลือก:

```text
Start
End
Path
```

กด:

```text
ตรวจสอบรายการ
```

Flow:

```text
UI
 ↓
POST /api/downloads/preview
 ↓
download_rep(dry_run=True)
 ↓
NHSO Search
 ↓
Filter
 ↓
Return files + stats
```

แสดง:

```text
พบ REP พร้อมดาวน์โหลด 26 ไฟล์

มีอยู่ในโฟลเดอร์แล้ว 8
ไฟล์ที่จะดาวน์โหลดใหม่ 18
```

หมายเหตุ:

เพื่อรู้ `exists` ใน dry run อาจต้องเพิ่ม check destination ใน preview logic

ระบบเดิม dry-run ไม่ increment exists เพราะ skip ก่อน `download_file()`

Codex ควรปรับ preview logic ให้สามารถ classify:

```text
matched
already_exists
will_download
```

โดยไม่เขียนไฟล์

---

# 53. Preview Result Contract

แนะนำ:

```json
{
  "stats": {
    "matched": 26,
    "already_exists": 8,
    "will_download": 18
  },
  "files": [
    {
      "output_name": "...",
      "exists": true
    }
  ]
}
```

---

# 54. Actual Download Confirmation

หลัง preview:

```text
พบ 26 รายการ
มีอยู่แล้ว 8
จะดาวน์โหลด 18

[เริ่มดาวน์โหลด]
```

ถ้า overwrite:

```text
คำเตือน: เปิดการเขียนทับไฟล์เดิม
```

---

# 55. Overwrite Safety UX

Checkbox:

```text
[ ] เขียนทับไฟล์ที่มีอยู่แล้ว
```

ถ้า check:

แสดง warning

ไม่ต้อง modal confirmation ซ้ำทุกครั้งใน Phase 1 แต่ควร style ชัดเจน

---

# 56. Insecure SSL

ระบบเดิมมี `--insecure`

Web UI ไม่ควรแสดง checkbox นี้ในหน้า main สำหรับผู้ใช้ทั่วไป

ไว้ใน:

```text
Advanced Settings
```

พร้อม warning:

```text
ปิดการตรวจสอบ SSL certificate
ใช้เฉพาะกรณีเครือข่ายของหน่วยงานมีปัญหา certificate
```

Default false หาก environment รองรับ

แต่ถ้าระบบปัจจุบันจำเป็นต้องใช้ insecure เป็นประจำ ต้องรักษา operational setting

---

# 57. Legacy Login

`legacy_login` ไม่ควรอยู่หน้า main

ให้ถือเป็น advanced/deprecated workflow

ห้ามส่ง username/password เข้า frontend หากไม่จำเป็น

หาก SSO ใช้งานได้ ให้ใช้ SSO เป็น default

---

# 58. Functional Requirements — MVP

MVP ต้องทำได้ทั้งหมด:

- [ ] เปิด Web App ผ่าน localhost
- [ ] ตรวจ NHSO SSO status
- [ ] Login NHSO ผ่าน Chrome
- [ ] เลือก start date
- [ ] เลือก end date
- [ ] กำหนด destination
- [ ] Preview/Dry Run
- [ ] แสดง matched files
- [ ] Download
- [ ] Skip existing files
- [ ] Optional overwrite
- [ ] แสดง statistics
- [ ] แสดง error ชัดเจน
- [ ] เก็บ job history
- [ ] ดู history ย้อนหลัง
- [ ] CLI เดิมยังใช้ได้

---

# 59. Non-functional Requirements

## Reliability

ระบบเดิมทำงานได้ต้องไม่เสื่อม

## Safety

ห้าม overwrite โดย default

## Security

DPAPI + localhost

## Maintainability

Core logic แยกจาก UI

## Observability

มี logs + job stats

## Usability

ผู้ใช้ไม่ต้องใช้ PowerShell

---

# 60. Unit Tests

Codex ต้องเพิ่ม tests ที่ไม่ยิง NHSO จริง

อย่างน้อย:

## Date token

```python
allowed_date_tokens("2026-05-01", "2026-05-01")
```

ต้องมี:

```text
25690501
```

---

## Output name

```text
ABC.ecd
→
ABC_REP.xls
```

---

## Ready status

test:

```python
{"loaded": "Y"}
```

และ:

```python
{"dataStatus": "1"}
```

---

## Validation

- invalid date
- start > end
- empty path
- invalid page size

---

# 61. Mocked Service Tests

Mock:

```python
search_page()
download_file()
auth_info()
refresh_token()
```

Test:

```text
page 0 → 2 items
page ends
1 matched
1 date skip
```

assert stats

---

# 62. API Tests

FastAPI TestClient

test:

```text
GET /api/health
```

200

test invalid date:

```text
POST /api/downloads/preview
```

400/422

---

# 63. Manual Acceptance Tests

## Case 1

Valid SSO + dry run

Expected:

preview สำเร็จ

---

## Case 2

Actual download

Expected:

file ถูกสร้าง

---

## Case 3

Run same range again

Expected:

exists count เพิ่ม

---

## Case 4

Overwrite

Expected:

ไฟล์ถูกเขียนใหม่

---

## Case 5

Expired token

Expected:

UI แสดง login required

---

## Case 6

No write permission

Expected:

error understandable

---

## Case 7

Network disconnect

Expected:

retry

แล้ว failed อย่าง graceful

---

# 64. Definition of Done สำหรับแต่ละ Phase

Codex ห้ามบอกว่า phase เสร็จเพียงเพราะ code compile

ต้องรายงาน:

```text
Files changed
What changed
Tests run
Test results
Known limitations
Manual test required
Rollback method
```

---

# 65. Required Codex Working Style

ทุก Phase:

1. อ่าน relevant files ก่อน
2. สรุป current behavior
3. แสดง implementation plan
4. แก้เฉพาะ scope ของ phase
5. run syntax/test
6. report diff summary
7. อย่า refactor unrelated code
8. อย่าลบ working behavior
9. preserve backward compatibility
10. ถ้ามี destructive action ให้หยุด

---

# 66. Git strategy

แนะนำ commits:

```text
chore: baseline nhso rep downloader
refactor: extract rep download service
test: add core downloader regression tests
feat: add fastapi application
feat: add rep download web ui
feat: add download job manager
feat: add sqlite download history
feat: add settings and date presets
```

อย่ารวมทุกอย่างใน commit เดียว

---

# 67. Suggested Phase Sequence for Codex

## Phase A

Baseline + backup

## Phase B

Extract `download_rep()`

## Phase C

Refactor CLI to call service

## Phase D

Add unit tests

## Phase E

FastAPI health + homepage

## Phase F

Auth status + SSO login button

## Phase G

Preview endpoint

## Phase H

Actual download endpoint

## Phase I

Job progress

## Phase J

SQLite history

## Phase K

UI polish

## Phase L

Launcher/package

---

# 68. Important Architectural Decision

อย่าทำ:

```text
Web App
  ↓
PowerShell
  ↓
Python script
```

ทำ:

```text
Web App
  ↓
Python Service
```

CLI เป็นเพียง adapter

```text
CLI
 ↓
Python Service
```

---

# 69. Future Phase — Automatic Monthly Download

หลังระบบ stable

สามารถเพิ่ม Scheduler

ตัวอย่าง:

```text
ทุกวันที่ 5
   ↓
คำนวณเดือนก่อนหน้า
   ↓
Preview
   ↓
Download missing REP
   ↓
History
```

แต่ automatic SSO renewal มีข้อจำกัด

ถ้า session หมด:

```text
job = login_required
```

อย่าพยายาม bypass NHSO authentication

---

# 70. Future Phase — Notifications

สามารถเพิ่ม:

- LINE messaging integration
- Email
- desktop notification

ตัวอย่าง:

```text
ดาวน์โหลด REP เดือน พ.ค. 2569 เสร็จแล้ว

พบ 26
ดาวน์โหลด 18
มีอยู่แล้ว 8
ผิดพลาด 0
```

ต้องไม่ส่งข้อมูลผู้ป่วย/filename ที่ sensitive หากไม่จำเป็น

---

# 71. Future Phase — Integration with Reconciliation System

หลัง REP ดาวน์โหลดแล้ว

สามารถต่อ workflow:

```text
REP Download
    ↓
Verify file
    ↓
Import REP
    ↓
rcmdb
    ↓
AR Reconciliation
```

แต่ต้องเป็น Phase แยก

ห้ามให้ Download MVP ไปแก้ฐานข้อมูล AR โดยอัตโนมัติ

---

# 72. Future Phase — MariaDB

SQLite ใช้สำหรับ local job history ก่อน

หากหลายเครื่อง/หลายผู้ใช้:

```text
FastAPI Server
   ↓
MariaDB
```

แต่ก่อนทำต้อง redesign:

- authentication
- user roles
- network security
- token ownership
- job runner host

เพราะ DPAPI token ผูกกับ Windows user/machine

---

# 73. Why Local Web App First

เหตุผล:

1. DPAPI ผูก Windows user
2. Playwright เปิด Chrome บนเครื่องนั้น
3. download destination เป็น local/Windows folder
4. NHSO session อยู่กับเครื่อง
5. ลด network exposure
6. deployment ง่าย

ดังนั้น Phase แรก:

```text
127.0.0.1:8000
```

เหมาะที่สุด

---

# 74. UI Page Structure

## `/`

Dashboard + Download form

## `/history`

History

## `/jobs/{id}`

Job detail

## `/settings`

Settings

ไม่ต้องมี SPA framework

Bootstrap + server templates เพียงพอ

---

# 75. Dashboard Cards

แนะนำ:

```text
NHSO Session
Last Download
Downloaded This Month
Failed Jobs
```

อย่าเพิ่ม dashboard analytics มากก่อน data history มีจริง

---

# 76. Main Download Form

Fields:

```text
Preset
Start Date
End Date
Destination
Overwrite
```

Buttons:

```text
Login NHSO
Preview
Start Download
```

---

# 77. Visual Status

ใช้ badge:

```text
Ready
Login Required
Running
Completed
Partial Error
Failed
```

สีเป็นเรื่อง UI เท่านั้น

อย่าพึ่ง business logic กับสี

---

# 78. File List

Preview:

| # | REP File | Local File | Existing | Action |
|---|---|---|---|---|

Action:

```text
Download
Skip
Overwrite
```

Phase 1 สามารถใช้ global overwrite แทน per-file overwrite

---

# 79. Cancellation

ไม่จำเป็น MVP

ถ้าจะเพิ่ม:

ต้อง implement cooperative cancellation

อย่า kill Python process แบบ force เพราะอาจทิ้ง `.part`

---

# 80. `.part` Cleanup

เมื่อ start job

สามารถตรวจ `.part` stale files

แต่ห้าม delete โดยอัตโนมัติจนกำหนด policy

Phase หลังอาจ:

```text
*.part older than 24h
```

แสดงให้ user เลือกลบ

---

# 81. Audit Trail

History ควรเก็บ:

```text
who
```

ไม่จำเป็นใน localhost single-user MVP

ถ้าหลาย user จึงเพิ่ม authentication และ username

---

# 82. Thai Language

UI หลักใช้ภาษาไทย

Technical log สามารถอังกฤษ

ตัวอย่าง:

```text
กำลังตรวจสอบ NHSO...
พบรายการ REP 26 รายการ
ดาวน์โหลดสำเร็จ 18 รายการ
มีไฟล์อยู่แล้ว 8 รายการ
```

---

# 83. Date Display

Backend/database:

```text
2026-05-01
```

UI อาจแสดง:

```text
01/05/2569
```

แต่ห้ามเก็บ พ.ศ. แบบ text ผสมใน backend date logic

---

# 84. Hospital Code

Prefer:

1. NHSO SSO account hcode
2. explicit setting only if necessary

หาก config hcode ต่างจาก SSO hcode:

แสดง warning

อย่าดาวน์โหลดข้ามหน่วยบริการโดยเงียบ

---

# 85. Configuration migration

ห้ามทำ migration destructive กับ `settings.dat`

อ่าน legacy ได้

Web settings แยกใหม่

จนกว่าจะมี migration plan พร้อม tests

---

# 86. Requirements file

Codex ต้อง inspect requirements ปัจจุบัน

เพิ่มเฉพาะที่จำเป็น

อย่า upgrade ทุก dependency แบบ major ในครั้งเดียว

---

# 87. README

เมื่อ Web App MVP เสร็จ

update README_TH.md ให้มี:

```text
วิธีติดตั้ง
วิธีเริ่ม Web App
วิธี Login NHSO
วิธี Preview
วิธี Download
ความหมาย Overwrite
วิธีแก้ SSO expired
ตำแหน่ง logs
ตำแหน่ง database
วิธี fallback ไปใช้ CLI
```

---

# 88. Operational Recovery

ถ้า Web App มีปัญหา

CLI เดิมยังต้องใช้ได้

นี่คือเหตุผลที่ backward compatibility สำคัญ

---

# 89. Rollback

ก่อน phase ใหญ่:

Git commit

ถ้าพัง:

```powershell
git diff
git status
```

อย่าใช้:

```text
git reset --hard
```

โดยไม่ยืนยันว่าผู้ใช้ไม่มีงานอื่น

---

# 90. Performance

ไม่ต้อง optimize ก่อน

แต่ต้อง:

- ไม่โหลดไฟล์ REP ทั้งหมดเข้า memory โดยไม่จำเป็น
- ปิด response
- ใช้ existing pagination
- ไม่ download parallel มากเกินไป

---

# 91. NHSO Rate Safety

คง sequential download + retry

อย่าเพิ่ม concurrency download 10–20 threads โดยไม่ได้ทดสอบ/อนุมัติ

อาจทำให้ NHSO rate limit

---

# 92. Test Environment

ถ้าไม่มี staging NHSO:

ใช้ dry-run และ mocks เป็นหลัก

actual download ทดสอบช่วงเล็ก

---

# 93. Recommended First Real Test

เลือกวันเดียว:

```text
start = 2026-05-01
end   = 2026-05-01
```

dry run ก่อน

แล้ว actual ถ้ารายการเหมาะสม

---

# 94. Source of Truth

Codex ต้องถือ source code ที่อยู่ใน repository ปัจจุบันเป็น source of truth

เอกสารนี้เป็น architecture/requirements

หาก code behavior จริงต่างจากเอกสาร:

1. อย่าเดา
2. inspect code
3. report discrepancy
4. preserve known-working behavior
5. แก้ requirement implementation ให้สอดคล้อง

---

# 95. สิ่งที่ Codex ต้องไม่ทำในรอบแรก

- ห้าม Dockerize
- ห้ามย้ายขึ้น cloud
- ห้าม React/Vue ถ้าไม่จำเป็น
- ห้าม Redis/Celery
- ห้าม PostgreSQL/MariaDB ตั้งแต่ MVP
- ห้าม OAuth สำหรับ Web App
- ห้าม rewrite NHSO authentication
- ห้ามเปลี่ยน token storage
- ห้าม download parallel
- ห้ามลบ CLI
- ห้าม auto schedule ก่อน manual flow stable

---

# 96. MVP Technology Stack

```text
Windows
Python 3.10+
FastAPI
Uvicorn
Jinja2
Bootstrap 5
Vanilla JavaScript
SQLite
Requests
Playwright
Windows DPAPI
```

---

# 97. Recommended Coding Standards

- type hints
- docstrings สำหรับ public/service functions
- small functions
- no giant route handlers
- API schemas separated
- no business logic in templates
- no hardcoded credentials
- pathlib for paths
- structured return objects
- logging instead of print where practical
- tests for pure logic

---

# 98. Example Service Layer API

```python
class RepDownloadService:

    def check_auth_status(self):
        ...

    def login_sso(self):
        ...

    def preview(self, request):
        ...

    def download(self, request, progress_callback=None):
        ...
```

ไม่บังคับต้องใช้ class

functional design ก็ได้

แต่ separation ต้องชัด

---

# 99. Example Internal Data Model

```python
@dataclass
class DownloadOptions:
    start_date: date
    end_date: date
    destination: Path
    overwrite: bool = False
    dry_run: bool = False
    insecure: bool = False
    page_size: int = 3000
```

ช่วยลด parameter soup ในอนาคต

---

# 100. Acceptance Criteria — Final MVP

ระบบถือว่า MVP สำเร็จเมื่อ:

1. User double-click/start app ได้
2. Browser เปิดหน้า Web App
3. เห็น NHSO login status
4. Login NHSO ผ่าน Chrome ได้
5. เลือก start/end date ได้
6. ระบุ destination ได้
7. Preview REP ได้
8. เห็นจำนวน matched
9. กด Download ได้
10. Existing files ถูก skip โดย default
11. Overwrite ใช้ได้เมื่อเลือก
12. Download retry ยังทำงาน
13. `.part` mechanism ยังอยู่
14. SSO token ยังเก็บด้วย DPAPI
15. Token ไม่ออก frontend/log
16. Progress/Status แสดงได้
17. Job result summary แสดงได้
18. History ถูกบันทึก SQLite
19. เปิดดูประวัติย้อนหลังได้
20. CLI เดิมยังใช้งานได้
21. มี unit/API tests
22. README อัปเดต
23. localhost only เป็น default
24. ไม่มี `shell=True` จาก user input
25. ไม่มี destructive operation

---

# 101. Master Task Prompt สำหรับ Codex

Codex ให้ใช้ข้อความนี้เป็นคำสั่งหลัก:

> คุณกำลังพัฒนา NHSO REP Download Manager จาก Python CLI เดิมให้เป็น Local Web Application บน Windows
>
> ก่อนแก้ไขใด ๆ ให้อ่าน `nhso_rep_paginated_download.py`, `README_TH.md`, `requirements.txt` และไฟล์ที่เกี่ยวข้องทั้งหมดใน repository
>
> ระบบเดิมใช้งานจริงอยู่แล้ว จึงต้อง refactor แบบ incremental และรักษาพฤติกรรมเดิมทั้งหมด โดยเฉพาะ:
>
> - NHSO OSS/SSO
> - Windows DPAPI token encryption
> - Playwright Chrome login
> - token refresh
> - hospital hcode resolution
> - pagination
> - date token filtering
> - ready status filtering
> - existing-file skip
> - overwrite option
> - retry logic
> - `.part` temporary file
> - CLI backward compatibility
>
> ห้าม rewrite NHSO integration จากศูนย์
>
> ห้ามเก็บ token หรือ password ใน frontend, SQLite หรือ log
>
> ห้ามใช้ shell command ที่ concatenate user input
>
> Phase แรกต้อง bind Web App เฉพาะ `127.0.0.1`
>
> ให้ทำงานทีละ Phase ตามเอกสารนี้ โดยทุก Phase ต้อง:
>
> 1. inspect current state
> 2. summarize current behavior
> 3. create backup or confirm Git safety
> 4. explain planned changes
> 5. implement only current phase
> 6. run syntax/tests
> 7. show results
> 8. report changed files
> 9. report known limitations
> 10. preserve rollback path
>
> เริ่มจาก Phase 0 และ Phase 1 เท่านั้นก่อน:
>
> - baseline current CLI
> - backup
> - extract reusable `download_rep()` service
> - replace `SystemExit` inside reusable service with exceptions
> - return structured result
> - preserve existing CLI behavior
> - add unit tests for pure functions/refactor
>
> หลัง Phase 1 ให้หยุดและสรุปผลก่อนดำเนิน Phase Web App

---

# 102. Prompt สำหรับ Phase 0–1 โดยเฉพาะ

ใช้คำสั่งนี้กับ Codex หากต้องการเริ่มทันที:

> อ่าน repository ปัจจุบันทั้งหมดที่เกี่ยวข้องกับ NHSO REP downloader โดยเริ่มจาก `nhso_rep_paginated_download.py`, `README_TH.md`, `requirements.txt`
>
> เป้าหมายรอบนี้คือ Phase 0–1 เท่านั้น ห้ามสร้าง Web UI ก่อน
>
> ขั้นตอน:
>
> 1. ตรวจ current Git status และห้ามทำลาย uncommitted work
> 2. ตรวจว่า `nhso_rep_paginated_download.py` compile ได้
> 3. สรุป current CLI arguments และ current workflow
> 4. ทำ backup หรือ safe Git checkpoint
> 5. refactor download logic ออกจาก `main()` เป็น reusable service function เช่น `download_rep(...)`
> 6. service ต้องรับ start/end/path/hcode/page_size/overwrite/dry_run/insecure/sso_login/legacy_login/config
> 7. service ต้อง return structured result/stats แทนการพึ่ง stdout อย่างเดียว
> 8. เพิ่ม `matched` statistic
> 9. รักษา DPAPI, SSO, Playwright, token refresh, pagination, date filter, retry, `.part`, existing/overwrite behavior เดิม
> 10. ห้ามใช้ subprocess/shell เพื่อเรียก script จาก service
> 11. `main()` ต้องกลายเป็น CLI adapter ที่เรียก service
> 12. CLI command เดิมต้องยังใช้ได้
> 13. เพิ่ม unit tests สำหรับ pure logic และ mocked service behavior ที่เหมาะสม
> 14. run `py_compile` และ tests
> 15. แสดง diff summary และผลทดสอบ
>
> ห้าม actual overwrite หรือ destructive test โดยไม่ได้รับอนุญาต
>
> หากจำเป็นต้องทดสอบ NHSO จริง ให้ใช้ `--dry-run` ก่อน
>
> เมื่อ Phase 1 เสร็จ ให้หยุดและรายงานผล ห้ามเริ่ม FastAPI เองจนกว่าจะได้รับคำสั่งต่อ

---

# 103. Prompt สำหรับ Phase 2–4

> ทำ Phase Web App ต่อจาก core service ที่ผ่านการทดสอบแล้ว
>
> เป้าหมาย:
>
> - เพิ่ม FastAPI
> - localhost only
> - Jinja2 + Bootstrap
> - health endpoint
> - SSO status
> - SSO login
> - preview/dry-run
> - actual download form
>
> ห้ามเปลี่ยน core NHSO logic หากไม่จำเป็น
>
> UI ภาษาไทย
>
> ไม่ต้อง React/Vue
>
> ไม่ต้อง scheduler
>
> ยังไม่ต้อง multi-user
>
> ต้องเพิ่ม Pydantic validation
>
> ต้องไม่ส่ง token เข้า browser
>
> ต้อง test API ด้วย mocked core service
>
> หลังเสร็จสรุป:
>
> - files added
> - routes
> - test results
> - manual test steps
> - known limitations

---

# 104. Prompt สำหรับ Phase 5–7

> เพิ่ม Job Manager, progress polling, SQLite history และ settings
>
> Requirements:
>
> - 1 active NHSO download job เป็น default
> - POST download return job_id
> - GET job status
> - job logs แบบ sanitized
> - SQLite เก็บ job metadata และ file result
> - ห้ามเก็บ SSO token/password
> - history page
> - job detail page
> - default destination setting
> - date presets
> - monthly preset
> - preserve localhost security
>
> ใช้ thread/background execution ภายใน process แบบเรียบง่ายก่อน
>
> ไม่ต้อง Redis/Celery
>
> เพิ่ม migration/init database แบบปลอดภัย
>
> เพิ่ม tests
>
> report result ก่อน phase ถัดไป

---

# 105. Final Reminder to Codex

ระบบนี้เกี่ยวข้องกับระบบ NHSO ที่ใช้งานจริง

Priority order:

```text
1. ไม่ทำระบบเดิมพัง
2. รักษาความปลอดภัยของ SSO token
3. รักษาความถูกต้องของ REP
4. ป้องกัน overwrite โดยไม่ตั้งใจ
5. ทำ Web UI ให้ใช้งานง่าย
6. เพิ่ม feature หลัง core stable
```

เมื่อมีข้อสงสัย:

```text
preserve existing behavior
```

ก่อน

```text
invent new behavior
```

---

# 106. Expected Final User Experience

สุดท้ายผู้ใช้ควรทำงานได้แบบนี้:

```text
เปิดโปรแกรม
   ↓
Browser เปิด NHSO REP Download Manager
   ↓
ตรวจ NHSO session
   ↓
ถ้าหมดอายุ → Login NHSO
   ↓
เลือกช่วงวันที่
   ↓
เลือก Folder
   ↓
กด "ตรวจสอบรายการ"
   ↓
เห็น REP ที่พบ
   ↓
กด "เริ่มดาวน์โหลด"
   ↓
ดู Progress
   ↓
เห็น Downloaded / Existing / Failed
   ↓
เปิด History ดูย้อนหลัง
```

ผู้ใช้ไม่ต้องเปิด PowerShell และไม่จำเป็นต้องรู้ command-line arguments

แต่ผู้ดูแลระบบยังสามารถใช้ CLI เดิมเพื่อ troubleshooting หรือ fallback ได้

---

# 107. End State Architecture

```text
                     ┌─────────────────────┐
                     │      User           │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Browser / Web UI    │
                     │ 127.0.0.1:8000      │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ FastAPI             │
                     │ API + Templates     │
                     └──────────┬──────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │ Job Manager  │ │ SQLite       │ │ Settings     │
        └──────┬───────┘ └──────────────┘ └──────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ REP Download Service │
        └──────────┬───────────┘
                   │
         ┌─────────┼──────────────┐
         │         │              │
         ▼         ▼              ▼
     NHSO API   DPAPI Token    Playwright
         │                        │
         │                        ▼
         │                     Chrome
         │
         ▼
     REP Files
         │
         ▼
     D:\REP\...
```

---

# 108. สรุป

แนวทางที่ต้องใช้คือ:

```text
Refactor First
Web App Second
Automation Later
```

อย่าทำ:

```text
UI First → duplicate downloader → unstable system
```

ให้ทำ:

```text
Existing Downloader
      ↓
Reusable Service
      ↓
CLI + Tests
      ↓
FastAPI
      ↓
Web UI
      ↓
Job History
      ↓
Automation
```

นี่คือ architecture หลักที่ Codex ต้องยึดตลอดโครงการ

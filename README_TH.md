# NHSO REP Download Manager

Local Web Application สำหรับค้นหา ตรวจสอบ และดาวน์โหลดไฟล์ REP จาก NHSO e-Claim บน Windows โดยใช้ Download Engine เดียวกับ CLI เดิม

## ข้อกำหนด

- Windows 10/11
- Python 3.10 ขึ้นไป
- Google Chrome สำหรับ NHSO OSS/SSO

## ติดตั้ง

เปิด PowerShell ในโฟลเดอร์โปรแกรมแล้วรัน:

```powershell
python -m pip install -r .\requirements.txt
```

หากเครื่องไม่มี Google Chrome ให้ติดตั้ง Playwright Chromium เพิ่ม:

```powershell
python -m playwright install chromium
```

Bootstrap และ Lucide ถูกเก็บในโปรเจกต์แล้ว หน้า Web App จึงไม่ต้องเชื่อม CDN

## เริ่ม Web App

Double-click:

```text
Start NHSO REP Web App.cmd
```

หรือรัน:

```powershell
python .\run_webapp.py
```

Browser จะเปิดที่:

```text
http://127.0.0.1:8000
```

Web App bind เฉพาะ `127.0.0.1` และไม่เปิดรับเครื่องอื่นในเครือข่าย

## เข้าสู่ระบบ NHSO

1. เปิดหน้า Web App
2. กด `เข้าสู่ระบบ NHSO`
3. Chrome จะเปิดหน้าต่าง NHSO OSS
4. เข้าสู่ระบบจนกลับมาหน้า e-Claim
5. กลับมาที่ Web App และตรวจว่าสถานะเป็น `SSO พร้อมใช้งาน`

Token ถูกเข้ารหัสด้วย Windows DPAPI และเก็บที่:

```text
%APPDATA%\AutoRepNHSO\sso_token.dat
```

Token ใช้ได้เฉพาะ Windows user และเครื่องที่สร้าง ห้ามคัดลอกไปเครื่องอื่น

## ตรวจสอบรายการ REP

1. เลือก preset หรือกำหนดวันที่เริ่มต้นและสิ้นสุด
2. ระบุโฟลเดอร์ปลายทาง
3. กด `ตรวจสอบรายการ`

Preview เป็น Dry Run ระบบจะค้นหาและแสดง matched/existing โดยไม่เขียนไฟล์ REP

## ดาวน์โหลด REP

หลังตรวจสอบรายการ กด `เริ่มดาวน์โหลด` ระบบจะสร้าง background job และแสดง progress กับ log ล่าสุด

- ดาวน์โหลดทำงานทีละหนึ่ง job
- ไฟล์เดิมถูกข้ามเป็นค่าเริ่มต้น
- ดาวน์โหลดเป็นลำดับ ไม่ยิง NHSO พร้อมกันหลาย thread
- ไฟล์ถูกเขียนเป็น `.part` ก่อน replace เป็นไฟล์จริง

## Overwrite

ค่าเริ่มต้นปิดอยู่ หากเปิด `เขียนทับไฟล์เดิม` ระบบจะแสดง confirmation ก่อนเริ่มงาน

ไม่ควรเปิด Overwrite หากไม่จำเป็น

## SSO หมดอายุ

หากแสดง `SSO หมดอายุ` หรือ `ต้องเข้าสู่ระบบ`:

1. กด `เข้าสู่ระบบ NHSO`
2. Login ผ่าน Chrome ใหม่
3. ตรวจสอบรายการอีกครั้ง

ระบบไม่เก็บ username/password ใน Web App, SQLite หรือ browser storage

## ประวัติ

เปิดเมนู `ประวัติ` เพื่อดู:

- ช่วงวันที่
- โฟลเดอร์ปลายทาง
- Matched / Downloaded / Existing / Failed
- สถานะ job
- รายการไฟล์ของแต่ละ job

SQLite เก็บเฉพาะ metadata และ file result ที่:

```text
data\app.db
```

ไม่มี token, password หรือเนื้อหาไฟล์ REP ในฐานข้อมูล

## ตั้งค่า

เมนู `ตั้งค่า` รองรับ:

- โฟลเดอร์เริ่มต้น
- Page size
- ค่าเริ่มต้น Insecure SSL
- วันที่ใช้งานล่าสุด

Web settings เก็บแยกจาก legacy settings ที่:

```text
data\webapp_settings.json
```

## Logs

Application log:

```text
logs\webapp.log
```

Job log ล่าสุดดูได้จากหน้า download ระหว่างงานทำงาน ข้อความถูก sanitize ก่อนเก็บใน memory

## ใช้ CLI เป็น fallback

Dry Run:

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --dry-run --insecure
```

ดาวน์โหลดจริง:

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --insecure
```

Login ใหม่ผ่าน CLI:

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-01 --path "D:\REP\69\6906" --dry-run --insecure --sso-login
```

## ตำแหน่งข้อมูลสำคัญ

| รายการ | ตำแหน่ง |
|---|---|
| DPAPI SSO token | `%APPDATA%\AutoRepNHSO\sso_token.dat` |
| Legacy settings | `%APPDATA%\AutoRepNHSO\settings.dat` |
| Web settings | `data\webapp_settings.json` |
| Job history | `data\app.db` |
| Application logs | `logs\webapp.log` |

## ทดสอบ

```powershell
python -m unittest discover -s .\tests -v
python -m pip check
```

Tests ใช้ mocks และ temporary databases โดยไม่ยิง NHSO จริง

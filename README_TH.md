# NHSO REP Auto Download

สคริปต์ดาวน์โหลด REP จาก e-Claim ผ่านบัญชี NHSO OSS/SSO รองรับ Windows และ Python 3.10 ขึ้นไป

## ติดตั้งบนเครื่องใหม่

คัดลอกไฟล์ต่อไปนี้ไปไว้ในโฟลเดอร์เดียวกัน:

- `nhso_rep_paginated_download.py`
- `requirements.txt`

เปิด PowerShell ที่โฟลเดอร์ดังกล่าว แล้วติดตั้ง dependency:

```powershell
python -m pip install -r .\requirements.txt
python -m playwright install chromium
```

ถ้าเครื่องมี Google Chrome อยู่แล้ว คำสั่งติดตั้ง Chromium บรรทัดที่สองไม่จำเป็น

## เข้าสู่ระบบครั้งแรก

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --dry-run --insecure --sso-login
```

Chrome จะเปิดขึ้นมา ให้เข้าสู่ระบบ OSS จนกลับมาหน้า e-Claim โปรแกรมจะเก็บ token ด้วย Windows DPAPI ที่ `%APPDATA%\AutoRepNHSO\sso_token.dat`

Token ใช้ได้เฉพาะ Windows user และเครื่องที่สร้าง token เท่านั้น ห้ามคัดลอก `sso_token.dat` ไปใช้เครื่องอื่น ให้รัน `--sso-login` ใหม่บนแต่ละเครื่อง

## ดาวน์โหลดจริง

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --insecure
```

โปรแกรมข้ามไฟล์ที่มีอยู่แล้ว ถ้าต้องการเขียนทับให้เพิ่ม `--overwrite`

## ตรวจรายการโดยไม่ดาวน์โหลด

```powershell
python .\nhso_rep_paginated_download.py --start 2026-05-01 --end 2026-05-31 --path "D:\REP\69\6906" --dry-run --insecure
```

ถ้า SSO session หมดอายุ ให้เพิ่ม `--sso-login` และเข้าสู่ระบบใหม่

## ตัวเลือก settings

ไม่จำเป็นต้องคัดลอก `settings.dat` ไปเครื่องใหม่ โปรแกรมอ่าน hcode จากบัญชี SSO ได้อัตโนมัติเมื่อระบุ `--start`, `--end` และ `--path`

หากต้องการใช้ไฟล์ JSON สามารถสร้าง `settings.json` เช่น:

```json
{
  "hcode": "11066",
  "start_date": "2026-05-01",
  "end_date": "2026-05-31",
  "path": "D:\\REP\\69\\6906",
  "overwrite": false
}
```

แล้วเรียกด้วย `--config .\settings.json`

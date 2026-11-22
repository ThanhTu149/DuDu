# Quy ước làm việc của repo DuDu

## Nguyên tắc một câu

**Sửa gì cũng phải commit và push lên `origin/main` — không để thay đổi nằm lại máy.**

Lý do: giảng viên và người chấm mở GitHub để xem, nên code trên GitHub phải là bản mới nhất.
Máy cá nhân không tính.

## Quy trình chuẩn mỗi lần sửa

```powershell
# 1. Chạy kiểm thử trước khi commit
python -m unittest discover -s tests -v
node --check web/assets/app.js

# 2. Commit + push kèm kiểm tra đồng bộ
powershell -ExecutionPolicy Bypass -File tools/push.ps1 "web: mô tả thay đổi"
```

`tools/push.ps1` làm ba việc: chạy kiểm thử, commit toàn bộ thay đổi, push rồi **so sánh
`local` với `remote`** — nếu lệch sẽ báo đỏ và trả mã lỗi.

## Kiểm tra nhanh trạng thái

```powershell
git fetch origin
git rev-parse --short HEAD        # local
git rev-parse --short origin/main # remote
git log origin/main..HEAD --oneline   # rỗng = đã push hết
git status --porcelain            # rỗng = không có gì chưa commit
```

## Móc chặn push khi test hỏng (tuỳ chọn, cài một lần)

```powershell
powershell -ExecutionPolicy Bypass -File tools/install-hooks.ps1
```

Sau đó mỗi lần `git push`, Git sẽ chạy bộ kiểm thử trước; test hỏng thì push bị chặn.
Móc này nằm trong `.git/hooks` nên chỉ áp dụng cho máy đang cài, không vào repo.

## Quy ước commit

- Tiền tố theo mảng: `web:`, `backend:`, `ml:`, `docs:`, `assets:`, `test:`, `fix:`, `data:`.
- Một commit một việc; câu mô tả tiếng Việt, nêu cái thay đổi chứ không phải "update".
- Không commit: mô hình `.joblib`, dữ liệu thô, báo cáo/slide, file tạm (`.gitignore` đã chặn).

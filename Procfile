# Di folder backend
cd backend

# 1. Buat runtime.txt
echo "python-3.11.9" > runtime.txt

# 2. Buat railway.toml
cat > railway.toml << 'EOF'
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn backend.wsgi --log-file -"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
EOF

# 3. Cek isi file
cat runtime.txt
cat railway.toml

# 4. Add, commit, push
git add runtime.txt railway.toml
git commit -m "Add railway.toml and runtime.txt for deployment"
git push origin main
```

---

## ✅ **Verifikasi Isi File:**

**runtime.txt** harus berisi:
```
python-3.11.9
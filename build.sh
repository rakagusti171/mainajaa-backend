#!/usr/bin/env bash
# build.sh

# Keluar jika ada error
set -o errexit

# 1. Install semua paket
pip install -r requirements.txt

# 2. Kumpulkan file statis (untuk Admin)
python manage.py collectstatic --no-input

# 3. Jalankan migrasi database
python manage.py migrate
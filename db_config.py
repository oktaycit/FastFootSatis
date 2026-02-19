# -*- coding: utf-8 -*-
"""
PostgreSQL Bağlantı Ayarları
"""

import os

# PostgreSQL Bağlantı Bilgileri
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'fastfoot_db',
    'user': 'fastfoot_user',
    'password': 'fastfoot_pass'
}

# Alternatif: Çevre değişkenlerinden oku
# DB_CONFIG = {
#     'host': os.getenv('DB_HOST', 'localhost'),
#     'port': int(os.getenv('DB_PORT', 5432)),
#     'database': os.getenv('DB_NAME', 'fastfoot_db'),
#     'user': os.getenv('DB_USER', 'fastfoot_user'),
#     'password': os.getenv('DB_PASSWORD', 'fastfoot_pass')
# }

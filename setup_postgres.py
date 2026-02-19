# -*- coding: utf-8 -*-
"""
PostgreSQL Kurulum ve Test Scripti
"""

import subprocess
import sys

def check_postgres_installed():
    """PostgreSQL kurulu mu kontrol et"""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ PostgreSQL kurulu: {result.stdout.strip()}")
            return True
        else:
            print("✗ PostgreSQL bulunamadı")
            return False
    except FileNotFoundError:
        print("✗ PostgreSQL bulunamadı")
        return False

def check_postgres_running():
    """PostgreSQL çalışıyor mu kontrol et"""
    try:
        result = subprocess.run(['pg_isready'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ PostgreSQL servisi çalışıyor")
            return True
        else:
            print("✗ PostgreSQL servisi çalışmıyor")
            print("  Başlatmak için: brew services start postgresql")
            return False
    except FileNotFoundError:
        print("✗ pg_isready komutu bulunamadı")
        return False

def setup_database():
    """Veri tabanı ve kullanıcı oluştur"""
    commands = [
        # Kullanıcı oluştur
        "CREATE USER fastfoot_user WITH PASSWORD 'fastfoot_pass';",
        # Veri tabanı oluştur
        "CREATE DATABASE fastfoot_db OWNER fastfoot_user;",
        # Yetkileri ver
        "GRANT ALL PRIVILEGES ON DATABASE fastfoot_db TO fastfoot_user;"
    ]
    
    print("\n=== Veri Tabanı Kurulumu ===")
    for cmd in commands:
        try:
            result = subprocess.run(
                ['psql', '-U', 'postgres', '-c', cmd],
                capture_output=True,
                text=True
            )
            if 'ERROR' in result.stderr and 'already exists' not in result.stderr:
                print(f"✗ Hata: {result.stderr}")
            else:
                print(f"✓ {cmd[:30]}...")
        except Exception as e:
            print(f"✗ Komut hatası: {e}")
    
    print("\n✓ Veri tabanı kurulumu tamamlandı")
    print("Bağlantı bilgileri:")
    print("  Database: fastfoot_db")
    print("  User: fastfoot_user")
    print("  Password: fastfoot_pass")
    print("  Host: localhost")
    print("  Port: 5432")

def test_connection():
    """Veri tabanı bağlantısını test et"""
    try:
        from database import db
        print("\n=== Bağlantı Testi ===")
        db.init_database()
        print("✓ Veri tabanı bağlantısı başarılı!")
        print("✓ Tüm tablolar oluşturuldu")
        return True
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")
        return False

def main():
    print("=== PostgreSQL Kurulum Kontrolü ===\n")
    
    # 1. PostgreSQL kurulu mu?
    if not check_postgres_installed():
        print("\n❌ PostgreSQL kurulu değil!")
        print("Kurulum için:")
        print("  macOS: brew install postgresql")
        print("  Linux: sudo apt-get install postgresql")
        return
    
    # 2. PostgreSQL çalışıyor mu?
    if not check_postgres_running():
        print("\n⚠️  PostgreSQL servisi başlatılmalı")
        print("macOS için: brew services start postgresql")
        return
    
    # 3. Veri tabanını oluştur
    print("\n" + "="*50)
    yanit = input("Veri tabanını oluşturmak ister misiniz? (e/h): ")
    if yanit.lower() == 'e':
        setup_database()
    
    # 4. Bağlantıyı test et
    print("\n" + "="*50)
    yanit = input("Bağlantıyı test etmek ister misiniz? (e/h): ")
    if yanit.lower() == 'e':
        test_connection()
    
    print("\n✓ Kurulum kontrolü tamamlandı!")

if __name__ == "__main__":
    main()

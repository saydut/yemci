# key_generator.py (Donanım Kilitli Versiyon)
# Bu betik, Yemci uygulaması için müşteriye özel lisans anahtarları üretir.
# SADECE GELİŞTİRİCİ KULLANIMI İÇİNDİR!

import wmi
import base64
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

PRIVATE_KEY_FILE = "private_key.pem"

def get_machine_id():
    """Bilgisayarın benzersiz donanım kimliğini (Anakart Seri Numarası) döndürür."""
    try:
        c = wmi.WMI()
        for board in c.Win32_BaseBoard():
            serial = board.SerialNumber.strip()
            if serial and "none" not in serial.lower(): return serial
        for processor in c.Win32_Processor():
            return processor.ProcessorId.strip()
    except Exception as e:
        print(f"Bu makinenin ID'si alınamadı: {e}")
    return "UNKNOWN_MACHINE_ID"


def load_private_key():
    """Mevcut özel anahtarı dosyadan yükler veya yenisini oluşturur."""
    try:
        with open(PRIVATE_KEY_FILE, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    except FileNotFoundError:
        print(f"'{PRIVATE_KEY_FILE}' bulunamadı. Sizin için yeni bir anahtar çifti oluşturuluyor...")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        
        # Özel anahtarı dosyaya kaydet
        with open(PRIVATE_KEY_FILE, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # AÇIK ANAHTARI (PUBLIC KEY) EKRANA YAZDIR
        public_key = private_key.public_key()
        pem_public = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        print("\n" + "="*55)
        print("!! ÖNEMLİ: AŞAĞIDAKİ AÇIK ANAHTARI KOPYALAYIN !!")
        print("Bu anahtarı yempyqt.py dosyasındaki PUBLIC_KEY_PEM değişkenine yapıştırın.")
        print("="*55)
        print(pem_public.decode('utf-8'))
        print("="*55 + "\n")
        
        return private_key

def create_license_key(duration_days, machine_id):
    """Belirtilen süre ve makine ID'si için bir lisans anahtarı oluşturur."""
    private_key = load_private_key()
    
    payload = f"machine_id:{machine_id};duration_days:{duration_days}"
    payload_bytes = payload.encode('utf-8')

    signature = private_key.sign(
        payload_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )

    license_key = base64.urlsafe_b64encode(payload_bytes).decode('utf-8') + "." + base64.urlsafe_b64encode(signature).decode('utf-8')
    return license_key

if __name__ == "__main__":
    print("Yemci Lisans Anahtarı Üretici (Donanım Kilitli)")
    print("="*45)
    
    # Anahtar dosyasının varlığını kontrol edip yüklemeyi tetikle
    load_private_key()
    
    print(f"Bu Bilgisayarın Makine Kodu: {get_machine_id()}")
    print("Müşterinizden alacağınız Makine Kodunu aşağıdaki alana girin.")
    
    customer_machine_id = input("Müşterinin Makine Kodu: ").strip()
    if not customer_machine_id:
        print("Makine kodu girmediniz. Çıkılıyor.")
    else:
        while True:
            print("\nLisans türünü seçin:")
            print("1: Aylık (30 gün)")
            print("2: Yıllık (365 gün)")
            print("q: Çıkış")
            
            choice = input("Seçiminiz: ")
            
            if choice == '1':
                key = create_license_key(30, customer_machine_id)
                print(f"\n--- {customer_machine_id} İÇİN AYLIK LİSANS ANAHTARI ---")
                print(key)
                print("-" * (len(customer_machine_id) + 35) + "\n")
            elif choice == '2':
                key = create_license_key(365, customer_machine_id)
                print(f"\n--- {customer_machine_id} İÇİN YILLIK LİSANS ANAHTARI ---")
                print(key)
                print("-" * (len(customer_machine_id) + 36) + "\n")
            elif choice.lower() == 'q':
                break
            else:
                print("Geçersiz seçim.")

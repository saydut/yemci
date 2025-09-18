# -*- coding: utf-8 -*-

import sys
import json
import os
import base64
import wmi
import win32crypt
from datetime import datetime, timedelta

# --- Gerekli Kütüphaneler ---
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QListWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QMenu, QDialog, QDialogButtonBox, QMessageBox, QFileDialog,
                             QStyle, QInputDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
import openpyxl

# --- Ayarlar ve Sabitler ---
# Ana veri ve yedekleme klasörleri
DATA_FILE = "data.json"
BACKUP_DIR = "backups"

# Programın gizli ayar dosyalarını saklayacağı klasör (C:\Users\KullaniciAdi\AppData\Roaming\YemciApp)
APP_CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'YemciApp')
# Şifrelenmiş lisans dosyasının tam yolu
SECURE_LICENSE_FILE = os.path.join(APP_CONFIG_DIR, 'license.bin')

# ÖNEMLİ: Bu anahtar, `key_generator.py` betiğini çalıştırdığınızda üretilen
# AÇIK ANAHTAR (public key) ile değiştirilmelidir.
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn5YFTK5h/miQOwVBvTAt
T2IX4SNBQgqJ1/lMlaJH7K2AoSuEYFqIgGB2EopPAKbxnI38I402EUxpJifopFIE
ExttIaWT5CHyGd4SNohZGyshkmudkbwVHq5Zw5eHtcQS9MCnB73E5q8DQKVYyxDf
JtcHcsr2dY7kUsUEvrOVjZkqYQm8ndl0jxvHZmw8zkuinUNs0QbNH46mm6cVEEGH
lBmoBvi4ptzUeINeKPzkoBn+VdnPgXqFfBvBIWoGmq0gnFaJNHmFh1yp9ZBSX+2G
q7apupXnpSEt46yjoP4C3YZAn9DQW8GiyY0/XJVfEiIPTsR7pe2MHQ2q6aNxZpzK
oQIDAQAB
-----END PUBLIC KEY-----
"""

# =============================================================================
# GÜVENLİK VE DONANIM FONKSİYONLARI
# =============================================================================
class SecureDataManager:
    """Windows DPAPI kullanarak verileri şifreler ve AppData'da saklar."""
    def __init__(self, file_path):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def write_data(self, data):
        try:
            encrypted_data = win32crypt.CryptProtectData(data.encode('utf-8'), None, None, None, None, 0)
            with open(self.file_path, 'wb') as f: f.write(encrypted_data)
            return True
        except Exception: return False

    def read_data(self):
        if not os.path.exists(self.file_path): return None
        try:
            with open(self.file_path, 'rb') as f: encrypted_data = f.read()
            _, decrypted_data = win32crypt.CryptUnprotectData(encrypted_data, None, None, None, 0)
            return decrypted_data.decode('utf-8')
        except Exception: return None

    def delete_file(self):
        if os.path.exists(self.file_path): os.remove(self.file_path)

def get_machine_id():
    """Bilgisayarın benzersiz donanım kimliğini (Anakart Seri Numarası) döndürür."""
    try:
        c = wmi.WMI()
        for board in c.Win32_BaseBoard():
            serial = board.SerialNumber.strip()
            if serial and "none" not in serial.lower(): return serial
        for processor in c.Win32_Processor():
            return processor.ProcessorId.strip()
    except Exception: pass
    return "UNKNOWN_MACHINE_ID"

# =============================================================================
# VERİ YÖNETİM SINIFI (JSON)
# =============================================================================
class DataManager:
    """Müşteri verilerini (data.json) yönetir."""
    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.companies = self.load_data()

    def load_data(self):
        if not os.path.exists(self.filename): return {}
        try:
            with open(self.filename, "r", encoding="utf-8") as f: data = json.load(f)
            return data
        except Exception: return {}

    def save_data(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.companies, f, ensure_ascii=False, indent=4)
        except Exception: pass

    def backup_data(self):
        if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(BACKUP_DIR, f"data_backup_{timestamp}.json")
        try:
            with open(self.filename, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            return True, backup_file
        except Exception as e: return False, str(e)

# =============================================================================
# ANA UYGULAMA PENCERESİ
# =============================================================================
class CariApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yemci Cari Hesap Yönetimi")
        self.setGeometry(100, 100, 1366, 768)
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_FileIcon))

        self.data_manager = DataManager()
        self.companies = self.data_manager.companies
        self.current_company = None
        self._sort_column = 5
        self._sort_order = Qt.DescendingOrder

        self._build_ui()
        self._update_company_list()

    # --- LİSANS KONTROL FONKSİYONLARI ---
    def verify_and_process_license(self, license_key):
        """Anahtarı doğrular, donanım kilidini kontrol eder ve lisansı kaydeder."""
        try:
            public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode('utf-8'))
            payload_b64, signature_b64 = license_key.split('.')
            payload = base64.urlsafe_b64decode(payload_b64)
            signature = base64.urlsafe_b64decode(signature_b64)
            public_key.verify(signature, payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
            parts = dict(part.split(':', 1) for part in payload.decode('utf-8').split(';'))

            key_machine_id = parts.get('machine_id')
            current_machine_id = get_machine_id()
            if key_machine_id != current_machine_id:
                QMessageBox.critical(self, "Lisans Hatası", f"Bu lisans anahtarı başka bir bilgisayara aittir.\n\nSizin Makine Kodunuz: {current_machine_id}")
                return 0

            license_data_to_save = f"{license_key}:::{datetime.now().strftime('%Y-%m-%d')}"
            s_manager = SecureDataManager(SECURE_LICENSE_FILE)
            s_manager.write_data(license_data_to_save)
            return 1
        except Exception:
            QMessageBox.critical(self, "Lisans Hatası", "Girdiğiniz lisans anahtarı geçersiz veya bozuk.")
            return 0

    def check_license_at_startup(self):
        """Program başlarken şifreli lisans dosyasını kontrol eder."""
        s_manager = SecureDataManager(SECURE_LICENSE_FILE)
        secure_data = s_manager.read_data()
        if secure_data and ":::" in secure_data:
            license_key, activation_date_str = secure_data.split(":::")
            try:
                public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode('utf-8'))
                payload_b64, signature_b64 = license_key.split('.')
                payload = base64.urlsafe_b64decode(payload_b64)
                public_key.verify(base64.urlsafe_b64decode(signature_b64), payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
                parts = dict(part.split(':', 1) for part in payload.decode('utf-8').split(';'))

                if parts.get('machine_id') != get_machine_id():
                    QMessageBox.critical(self, "Lisans Hatası", "Donanım değişikliği tespit edildi. Lütfen yeni bir lisans alın.")
                    s_manager.delete_file()
                    return self.prompt_for_new_license()

                duration_days = int(parts.get('duration_days', 0))
                expiration_date = datetime.strptime(activation_date_str, "%Y-%m-%d") + timedelta(days=duration_days)
                if datetime.now() > expiration_date:
                    QMessageBox.critical(self, "Lisans Hatası", f"Lisansınız {expiration_date.strftime('%d-%m-%Y')} tarihinde doldu.")
                    s_manager.delete_file()
                    return self.prompt_for_new_license()
                return True
            except Exception:
                s_manager.delete_file()
                return self.prompt_for_new_license()
        return self.prompt_for_new_license()

    def prompt_for_new_license(self):
        """Kullanıcıya yeni lisans anahtarı soran diyalog."""
        machine_id = get_machine_id()
        license_key, ok = QInputDialog.getText(self, "Lisans Etkinleştirme",
                                               f"Lütfen lisans anahtarınızı girin.\n\nMakine Kodunuz: {machine_id}\n(Bu kodu lisans almak için kullanın)")
        if ok and license_key and self.verify_and_process_license(license_key) == 1:
            QMessageBox.information(self, "Başarılı", "Lisans başarıyla etkinleştirildi!")
            return True
        return False

    # --- ARAYÜZ OLUŞTURMA VE YÖNETİMİ ---
    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(300)

        company_add_layout = QHBoxLayout()
        self.entry_company_name = QLineEdit()
        self.entry_company_name.setPlaceholderText("Yeni Müşteri Adı")
        self.entry_company_name.returnPressed.connect(self.add_company)
        company_add_layout.addWidget(self.entry_company_name)
        btn_add_company = QPushButton(self.style().standardIcon(QStyle.SP_FileDialogNewFolder), " Ekle")
        btn_add_company.clicked.connect(self.add_company)
        company_add_layout.addWidget(btn_add_company)
        left_layout.addLayout(company_add_layout)

        self.entry_search_company = QLineEdit()
        self.entry_search_company.setPlaceholderText("Müşteri Ara...")
        self.entry_search_company.textChanged.connect(self._filter_company_list)
        left_layout.addWidget(self.entry_search_company)

        left_layout.addWidget(QLabel("Müşteriler"))
        self.list_companies = QListWidget()
        self.list_companies.currentItemChanged.connect(self.on_company_select)
        left_layout.addWidget(self.list_companies)

        company_actions_layout = QHBoxLayout()
        btn_delete_company = QPushButton(self.style().standardIcon(QStyle.SP_TrashIcon), " Sil")
        btn_delete_company.clicked.connect(self.delete_selected_company)
        btn_backup_data = QPushButton(self.style().standardIcon(QStyle.SP_DialogSaveButton), " Yedekle")
        btn_backup_data.clicked.connect(self.backup_data)
        company_actions_layout.addWidget(btn_delete_company)
        company_actions_layout.addWidget(btn_backup_data)
        left_layout.addLayout(company_actions_layout)
        main_layout.addWidget(left_panel)

        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        main_layout.addWidget(self.right_panel)
        self._clear_details_frame()

    def _clear_details_frame(self):
        while self.right_layout.count():
            item = self.right_layout.takeAt(0)
            widget = item.widget()
            if widget is not None: widget.setParent(None)
        welcome_label = QLabel("Lütfen bir müşteri seçin veya yeni bir tane ekleyin.")
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("font-size: 18px; color: grey;")
        self.right_layout.addWidget(welcome_label)

    def _display_company_details(self, company_name):
        self._clear_details_frame()
        input_frame = QWidget()
        input_layout = QVBoxLayout(input_frame)
        purchase_layout = QHBoxLayout()
        purchase_layout.addWidget(QLabel("<b>Yem Alımı:</b>"))
        self.entry_yem, self.entry_adet, self.entry_fiyat = QLineEdit(), QLineEdit(), QLineEdit()
        self.entry_adet.setValidator(QDoubleValidator(0.00, 99999999.00, 2, self))
        self.entry_fiyat.setValidator(QDoubleValidator(0.00, 99999999.00, 2, self))
        purchase_layout.addWidget(QLabel("Yem Adı:")); purchase_layout.addWidget(self.entry_yem)
        purchase_layout.addWidget(QLabel("Adet:")); purchase_layout.addWidget(self.entry_adet)
        purchase_layout.addWidget(QLabel("Birim Fiyat:")); purchase_layout.addWidget(self.entry_fiyat)
        btn_add_purchase = QPushButton(self.style().standardIcon(QStyle.SP_DialogApplyButton), " Ekle")
        btn_add_purchase.clicked.connect(self._add_purchase)
        purchase_layout.addWidget(btn_add_purchase)
        input_layout.addLayout(purchase_layout)
        payment_layout = QHBoxLayout()
        payment_layout.addWidget(QLabel("<b>Ödeme:</b>"))
        self.entry_aciklama, self.entry_tutar = QLineEdit(), QLineEdit()
        self.entry_tutar.setValidator(QDoubleValidator(0.00, 99999999.00, 2, self))
        payment_layout.addWidget(QLabel("Açıklama:")); payment_layout.addWidget(self.entry_aciklama)
        payment_layout.addWidget(QLabel("Tutar:")); payment_layout.addWidget(self.entry_tutar)
        btn_add_payment = QPushButton(self.style().standardIcon(QStyle.SP_DialogApplyButton), " Ödeme Ekle")
        btn_add_payment.clicked.connect(self._add_payment)
        payment_layout.addWidget(btn_add_payment)
        input_layout.addLayout(payment_layout)
        self.right_layout.addWidget(input_frame)

        self.tree = QTableWidget()
        self.tree.setColumnCount(6)
        self.tree.setHorizontalHeaderLabels(["Tür", "Açıklama / Yem Adı", "Adet", "Birim Fiyat", "Toplam", "Tarih"])
        self.tree.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.doubleClicked.connect(self._edit_selected_row)
        self.tree.horizontalHeader().sortIndicatorChanged.connect(self._sort_treeview)
        self.right_layout.addWidget(self.tree)

        bottom_layout = QHBoxLayout()
        self.total_label = QLabel("Toplam Bakiye: 0.00 TL")
        self.total_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        bottom_layout.addWidget(self.total_label)
        bottom_layout.addStretch()
        btn_export = QPushButton(self.style().standardIcon(QStyle.SP_ArrowUp), " Excel'e Aktar")
        btn_export.clicked.connect(self.export_to_excel)
        bottom_layout.addWidget(btn_export)
        self.right_layout.addLayout(bottom_layout)
        self._sort_and_update_treeview()

    # --- VERİ İŞLEME FONKSİYONLARI ---
    def add_company(self):
        name = self.entry_company_name.text().strip()
        if name and name not in self.companies:
            self.companies[name] = []
            self.entry_company_name.clear()
            self._update_company_list()
            self.data_manager.save_data()

    def delete_selected_company(self):
        if self.current_company and QMessageBox.question(self, "Onay", f"'{self.current_company}' müşterisini silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.companies.pop(self.current_company, None)
            self.current_company = None
            self._update_company_list()
            self._clear_details_frame()
            self.data_manager.save_data()

    def on_company_select(self, current, _):
        if current: self.current_company = current.text(); self._display_company_details(self.current_company)
        else: self.current_company = None; self._clear_details_frame()

    def _update_company_list(self):
        self.list_companies.clear()
        self.list_companies.addItems(sorted(self.companies.keys()))
        self._filter_company_list()

    def _filter_company_list(self):
        filter_text = self.entry_search_company.text().lower()
        for i in range(self.list_companies.count()):
            self.list_companies.item(i).setHidden(filter_text not in self.list_companies.item(i).text().lower())

    def _add_purchase(self):
        yem, adet, fiyat = self.entry_yem.text().strip(), self.entry_adet.text().replace(',', '.'), self.entry_fiyat.text().replace(',', '.')
        if not all([yem, adet, fiyat]): return
        try:
            adet_f, fiyat_f = float(adet), float(fiyat)
            rec = {"type": "purchase", "data": {"yem": yem, "adet": adet_f, "fiyat": fiyat_f, "toplam": adet_f * fiyat_f, "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
            self.companies[self.current_company].append(rec)
            self._sort_and_update_treeview()
            self.data_manager.save_data()
            self.entry_yem.clear(); self.entry_adet.clear(); self.entry_fiyat.clear()
        except ValueError: pass

    def _add_payment(self):
        aciklama, tutar = self.entry_aciklama.text().strip() or "Ödeme", self.entry_tutar.text().replace(',', '.')
        if not tutar: return
        try:
            tutar_f = float(tutar)
            rec = {"type": "payment", "data": {"aciklama": aciklama, "tutar": tutar_f, "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
            self.companies[self.current_company].append(rec)
            self._sort_and_update_treeview()
            self.data_manager.save_data()
            self.entry_aciklama.clear(); self.entry_tutar.clear()
        except ValueError: pass

    def _get_selected_record_and_row(self):
        selected_items = self.tree.selectedItems()
        if not selected_items: return None, -1
        # Sıralanmış listedeki indeksi döndür
        return self.companies[self.current_company][selected_items[0].row()], selected_items[0].row()

    def _edit_selected_row(self):
        record, row = self._get_selected_record_and_row()
        if not record: return
        dialog_class = EditPurchaseDialog if record["type"] == "purchase" else EditPaymentDialog
        dialog = dialog_class(self, record)
        if dialog.exec_() == QDialog.Accepted:
            self.companies[self.current_company][row] = dialog.get_data()
            self._sort_and_update_treeview()
            self.data_manager.save_data()

    def _delete_selected_row(self):
        _, row = self._get_selected_record_and_row()
        if row != -1 and QMessageBox.question(self, "Onay", "Seçili işlemi silmek istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            del self.companies[self.current_company][row]
            self._sort_and_update_treeview()
            self.data_manager.save_data()

    def _mark_as_paid(self):
        record, _ = self._get_selected_record_and_row()
        if record and record["type"] == "purchase":
            data = record["data"]
            if QMessageBox.question(self, "Onay", f"'{data['yem']}' alımını {data['toplam']:.2f} TL tutarında bir ödeme ile kapatmak istediğinize emin misiniz?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                rec = {"type": "payment", "data": {"aciklama": f"'{data['yem']}' alımı ödendi", "tutar": data['toplam'], "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
                self.companies[self.current_company].append(rec)
                self._sort_and_update_treeview()
                self.data_manager.save_data()

    def _sort_and_update_treeview(self):
        if not self.current_company: return
        key_map = lambda r: {0: r.get("type"), 1: r["data"].get("yem", r["data"].get("aciklama")), 2: r["data"].get("adet", 0), 3: r["data"].get("fiyat", 0), 4: r["data"].get("toplam", -r["data"].get("tutar", 0)), 5: datetime.strptime(r["data"]["tarih"], "%Y-%m-%d %H:%M:%S")}[self._sort_column]
        self.companies[self.current_company].sort(key=key_map, reverse=(self._sort_order == Qt.DescendingOrder))
        self._update_treeview(self.companies[self.current_company])

    def _update_treeview(self, records):
        self.tree.setSortingEnabled(False); self.tree.setRowCount(0)
        for row, rec in enumerate(records):
            self.tree.insertRow(row)
            data = rec["data"]
            items = []
            if rec["type"] == "purchase": items = ["Alış", data["yem"], f"{data['adet']}", f"{data['fiyat']:.2f}", f"{data['toplam']:.2f}", data["tarih"]]
            elif rec["type"] == "payment": items = ["Ödeme", data["aciklama"], "", "", f"-{data['tutar']:.2f}", data["tarih"]]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col in [2, 3, 4]: item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tree.setItem(row, col, item)
            if rec["type"] == "payment":
                for col in range(self.tree.columnCount()): self.tree.item(row, col).setForeground(Qt.red)
        self.tree.setSortingEnabled(True); self._update_total_label()

    def _update_total_label(self):
        if not self.current_company: return
        total = sum(rec["data"].get("toplam", 0) - rec["data"].get("tutar", 0) for rec in self.companies.get(self.current_company, []))
        self.total_label.setText(f"Toplam Bakiye: {total:.2f} TL")
        self.total_label.setStyleSheet(f"font-size: 16px; font-weight: bold; {'color: red;' if total > 0 else 'color: green;'}")

    def _sort_treeview(self, column, order):
        self._sort_column, self._sort_order = column, order
        self._sort_and_update_treeview()

    def _show_context_menu(self, pos):
        if self.tree.selectedItems():
            menu = QMenu()
            menu.addAction("Düzenle", self._edit_selected_row)
            menu.addAction("Sil", self._delete_selected_row)
            record, _ = self._get_selected_record_and_row()
            if record and record["type"] == "purchase":
                menu.addSeparator(); menu.addAction("Ödendi Olarak İşaretle", self._mark_as_paid)
            menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def export_to_excel(self):
        if not self.current_company: return
        filename, _ = QFileDialog.getSaveFileName(self, "Excel Olarak Kaydet", f"{self.current_company}_hesap_dokumu.xlsx", "Excel Dosyaları (*.xlsx)")
        if not filename: return
        try:
            wb, ws = openpyxl.Workbook(), openpyxl.Workbook().active
            ws = wb.active; ws.title = self.current_company
            ws.append(["Tür", "Açıklama / Yem Adı", "Adet", "Birim Fiyat (TL)", "Toplam (TL)", "Tarih"])
            for record in self.companies.get(self.current_company, []):
                data = record["data"]
                ws.append(["Alış", data["yem"], data["adet"], data["fiyat"], data["toplam"], data["tarih"]] if record["type"] == "purchase" else ["Ödeme", data["aciklama"], "", "", -data["tutar"], data["tarih"]])
            total = sum(r["data"].get("toplam", 0) - r["data"].get("tutar", 0) for r in self.companies[self.current_company])
            ws.append([]); ws.append(["", "", "", "TOPLAM BAKİYE:", total])
            wb.save(filename)
        except Exception: pass

    def backup_data(self):
        success, message = self.data_manager.backup_data()
        QMessageBox.information(self, "Başarılı" if success else "Hata", message)

    def closeEvent(self, event):
        self.data_manager.save_data()
        event.accept()

# =============================================================================
# DÜZENLEME PENCERELERİ
# =============================================================================
class EditPurchaseDialog(QDialog):
    def __init__(self, parent, old_record):
        super().__init__(parent)
        self.setWindowTitle("Yem Alışını Düzenle"); self.old_record = old_record
        data = old_record["data"]
        layout, form_layout = QVBoxLayout(self), QHBoxLayout()
        self.e_yem = QLineEdit(data["yem"]); self.e_adet = QLineEdit(str(data["adet"])); self.e_fiyat = QLineEdit(str(data["fiyat"]))
        self.e_adet.setValidator(QDoubleValidator(0.0, 999999.0, 2, self)); self.e_fiyat.setValidator(QDoubleValidator(0.0, 999999.0, 2, self))
        form_layout.addWidget(QLabel("Yem Adı:")); form_layout.addWidget(self.e_yem)
        form_layout.addWidget(QLabel("Adet:")); form_layout.addWidget(self.e_adet)
        form_layout.addWidget(QLabel("Birim Fiyat:")); form_layout.addWidget(self.e_fiyat)
        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def get_data(self):
        adet = float(self.e_adet.text().replace(',', '.')); fiyat = float(self.e_fiyat.text().replace(',', '.'))
        new_data = {"yem": self.e_yem.text().strip(), "adet": adet, "fiyat": fiyat, "toplam": adet * fiyat, "tarih": self.old_record["data"]["tarih"]}
        return {"type": "purchase", "data": new_data}

class EditPaymentDialog(QDialog):
    def __init__(self, parent, old_record):
        super().__init__(parent)
        self.setWindowTitle("Ödemeyi Düzenle"); self.old_record = old_record
        data = old_record["data"]
        layout, form_layout = QVBoxLayout(self), QHBoxLayout()
        self.e_aciklama = QLineEdit(data["aciklama"]); self.e_tutar = QLineEdit(str(data["tutar"]))
        self.e_tutar.setValidator(QDoubleValidator(0.0, 999999.0, 2, self))
        form_layout.addWidget(QLabel("Açıklama:")); form_layout.addWidget(self.e_aciklama)
        form_layout.addWidget(QLabel("Tutar:")); form_layout.addWidget(self.e_tutar)
        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def get_data(self):
        new_data = {"aciklama": self.e_aciklama.text().strip() or "Ödeme", "tutar": float(self.e_tutar.text().replace(',', '.')), "tarih": self.old_record["data"]["tarih"]}
        return {"type": "payment", "data": new_data}

# =============================================================================
# UYGULAMAYI BAŞLATMA
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget { font-size: 11pt; font-family: Arial; }
        QMainWindow { background-color: #f7f8fa; }
        QListWidget, QTableWidget { border: 1px solid #d3d3d3; border-radius: 5px; padding: 5px; background-color: white; }
        QPushButton { background-color: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
        QPushButton:hover { background-color: #0056b3; }
        QLineEdit { border: 1px solid #d3d3d3; border-radius: 4px; padding: 6px; }
        QHeaderView::section { background-color: #e9ecef; padding: 4px; border: 1px solid #d3d3d3; font-weight: bold; }
    """)

    main_window = CariApp()

    if main_window.check_license_at_startup():
        main_window.show()
        sys.exit(app.exec_())
    else:
        sys.exit()
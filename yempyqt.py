import sys
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QDialog,
    QDialogButtonBox, QMessageBox, QInputDialog, QAction
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QIcon, QDoubleValidator

# Veri dosyasının adı
DATA_FILE = "data.json"

class CariApp(QMainWindow):
    """
    Uygulamanın ana penceresi ve ana iş mantığını içeren sınıf.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yemci Cari Hesap - Şirket&Şahıs Bazlı")
        self.setGeometry(100, 100, 1200, 800)

        self.companies = {}  # {"ŞirketAdı": [ {type, data}, ... ]}
        self.current_company = None
        self._sort_column = None
        self._sort_order = Qt.AscendingOrder

        self._build_ui()
        self._load_data()
        
    def _build_ui(self):
        """Uygulamanın ana arayüzünü oluşturur."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # -------------------
        # Sol Panel: Şirket Listesi ve Yönetimi
        # -------------------
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(250)

        # Şirket Ekleme
        company_input_layout = QHBoxLayout()
        self.entry_company = QLineEdit()
        self.entry_company.setPlaceholderText("Yeni Şirket&Şahıs Adı")
        self.entry_company.returnPressed.connect(self.add_company)
        company_input_layout.addWidget(self.entry_company)
        
        btn_add_company = QPushButton("Ekle")
        btn_add_company.clicked.connect(self.add_company)
        company_input_layout.addWidget(btn_add_company)
        left_layout.addLayout(company_input_layout)

        # Şirket Listesi
        left_layout.addWidget(QLabel("Şirketler&Şahıslar"))
        self.list_companies = QListWidget()
        self.list_companies.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_companies.currentItemChanged.connect(self.on_company_select)
        left_layout.addWidget(self.list_companies)

        # Şirket Silme Butonu
        btn_delete_company = QPushButton("Seçili Şirketi&Şahsı Sil")
        btn_delete_company.clicked.connect(self.delete_selected_company)
        left_layout.addWidget(btn_delete_company)
        
        main_layout.addWidget(left_panel)

        # -------------------
        # Sağ Panel: Detaylar ve İşlemler
        # -------------------
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        main_layout.addWidget(self.right_panel)

        self._clear_details_frame()

    def _clear_details_frame(self):
        """Sağ paneldeki tüm widget'ları temizler."""
        for i in reversed(range(self.right_layout.count())):
            widget_to_remove = self.right_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        welcome_label = QLabel("Sol taraftan bir şirket seçin veya yeni bir tane ekleyin.")
        welcome_label.setAlignment(Qt.AlignCenter)
        self.right_layout.addWidget(welcome_label)

    def _display_company_details(self, company_name):
        """Belirli bir şirket için detay arayüzünü oluşturur."""
        self._clear_details_frame()

        # Üst Kısım: Giriş Alanları
        input_frame = QWidget()
        input_layout = QVBoxLayout(input_frame)
        
        # Yem Alımı
        purchase_layout = QHBoxLayout()
        purchase_layout.addWidget(QLabel("<b>Yem Alımı:</b>"))
        purchase_layout.addSpacing(10)
        purchase_layout.addWidget(QLabel("Yem Adı:"))
        self.entry_yem = QLineEdit()
        purchase_layout.addWidget(self.entry_yem)
        purchase_layout.addWidget(QLabel("Adet:"))
        self.entry_adet = QLineEdit()
        self.entry_adet.setValidator(self.get_float_validator())
        purchase_layout.addWidget(self.entry_adet)
        purchase_layout.addWidget(QLabel("Birim Fiyat:"))
        self.entry_fiyat = QLineEdit()
        self.entry_fiyat.setValidator(self.get_float_validator())
        purchase_layout.addWidget(self.entry_fiyat)
        btn_add_purchase = QPushButton("Ekle")
        btn_add_purchase.clicked.connect(self._add_purchase)
        purchase_layout.addWidget(btn_add_purchase)
        input_layout.addLayout(purchase_layout)
        
        # Ödeme Girişi
        payment_layout = QHBoxLayout()
        payment_layout.addWidget(QLabel("<b>Ödeme:</b>"))
        payment_layout.addSpacing(10)
        payment_layout.addWidget(QLabel("Açıklama:"))
        self.entry_aciklama = QLineEdit()
        payment_layout.addWidget(self.entry_aciklama)
        payment_layout.addWidget(QLabel("Tutar:"))
        self.entry_tutar = QLineEdit()
        self.entry_tutar.setValidator(self.get_float_validator())
        payment_layout.addWidget(self.entry_tutar)
        btn_add_payment = QPushButton("Ödeme Ekle")
        btn_add_payment.clicked.connect(self._add_payment)
        payment_layout.addWidget(btn_add_payment)
        input_layout.addLayout(payment_layout)

        self.right_layout.addWidget(input_frame)

        # Tablo
        self.tree = QTableWidget()
        self.tree.setColumnCount(6)
        self.tree.setHorizontalHeaderLabels(["Tür", "Açıklama / Yem Adı", "Adet", "Birim Fiyat", "Toplam", "Tarih"])
        self.tree.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.horizontalHeader().sortIndicatorChanged.connect(self._sort_treeview)
        
        # Sağ Tık Menüsü
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.doubleClicked.connect(self._edit_selected_row)

        self.right_layout.addWidget(self.tree)

        # Alt Kısım: Toplam ve İhracat Butonları
        bottom_frame = QWidget()
        bottom_layout = QHBoxLayout(bottom_frame)
        self.total_label = QLabel("Toplam: 0.00 TL")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        bottom_layout.addWidget(self.total_label)
        bottom_layout.addStretch()
        
        # Ekstralar için butonlar
        btn_export = QPushButton("Excel'e Aktar")
        # btn_export.clicked.connect(self.export_to_excel) # İleride eklenebilir
        btn_export.setDisabled(True) # Şimdilik pasif
        bottom_layout.addWidget(btn_export)
        
        self.right_layout.addWidget(bottom_frame)
        
        # Eğer veri varsa tabloyu doldur
        self._update_treeview()
        self._update_total_label()

    # -------------------
    # Veri Yönetimi Fonksiyonları
    # -------------------
    def add_company(self):
        """Yeni bir şirket oluşturur ve sol listeye ekler."""
        name = self.entry_company.text().strip()
        if not name:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir şirket&şahıs adı girin.")
            return
        if name in self.companies:
            QMessageBox.warning(self, "Uyarı", "Bu isimde bir şirket&şahıs zaten var.")
            return

        self.companies[name] = []
        self.entry_company.clear()
        self._update_company_list()
        
    def delete_selected_company(self):
        """Seçili şirketi ve tüm verilerini siler."""
        current_item = self.list_companies.currentItem()
        if not current_item:
            QMessageBox.information(self, "Bilgi", "Silmek için bir şirket&şahıs seçin.")
            return

        name = current_item.text()
        reply = QMessageBox.question(self, "Onay",
                                     f"'{name}' şirketini&şahısını ve tüm verilerini silmek istediğinize emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.companies.pop(name, None)
            self._update_company_list()
            self._clear_details_frame()

    def on_company_select(self, current, previous):
        """Şirket listesinden seçim yapıldığında tetiklenir."""
        if current:
            self.current_company = current.text()
            self._display_company_details(self.current_company)
        else:
            self.current_company = None
            self._clear_details_frame()

    def _update_company_list(self):
        """Şirket listesini alfabetik olarak sıralayıp günceller."""
        self.list_companies.clear()
        sorted_companies = sorted(self.companies.keys())
        self.list_companies.addItems(sorted_companies)
        self._save_data()

    def _update_treeview(self):
        """Belirli bir şirketin verilerini tabloya doldurur."""
        self.tree.setRowCount(0)
        if not self.current_company or self.current_company not in self.companies:
            return

        for rec in self.companies.get(self.current_company, []):
            row_count = self.tree.rowCount()
            self.tree.insertRow(row_count)
            self._add_row_to_treeview(row_count, rec)
        
        # Sütunları içeriğe göre yeniden boyutlandır
        self.tree.resizeColumnsToContents()

    def _add_row_to_treeview(self, row, rec):
        """Veri kaydını tabloya tek bir satır olarak ekler."""
        if rec["type"] == "purchase":
            vals = (
                "Alış",
                rec["data"]["yem"],
                f"{rec['data']['adet']}",
                f"{rec['data']['fiyat']:.2f}",
                f"{rec['data']['toplam']:.2f} TL",
                rec["data"]["tarih"]
            )
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                self.tree.setItem(row, col, item)
            
        elif rec["type"] == "payment":
            vals = (
                "Ödeme",
                rec["data"]["aciklama"],
                "",  # Adet
                "",  # Birim Fiyat
                f"-{rec['data']['tutar']:.2f} TL", # Tutar
                rec["data"]["tarih"]
            )
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                self.tree.setItem(row, col, item)
            
            # Ödeme satırını kırmızı yap
            for col in range(self.tree.columnCount()):
                self.tree.item(row, col).setForeground(Qt.red)

    def _update_total_label(self):
        """Seçili şirketin toplamını hesaplar ve etiketi günceller."""
        if not self.current_company:
            self.total_label.setText("Toplam: 0.00 TL")
            return
            
        total = 0.0
        for rec in self.companies.get(self.current_company, []):
            try:
                if rec["type"] == "purchase":
                    total += rec["data"]["toplam"]
                elif rec["type"] == "payment":
                    total -= rec["data"]["tutar"]
            except (KeyError, ValueError):
                pass
        self.total_label.setText(f"Toplam: {total:.2f} TL")

    def _add_purchase(self):
        """Yem alımı kaydı ekler."""
        yem = self.entry_yem.text().strip()
        adet_text = self.entry_adet.text().replace(',', '.')
        fiyat_text = self.entry_fiyat.text().replace(',', '.')

        if not yem or not adet_text or not fiyat_text:
            QMessageBox.warning(self, "Uyarı", "Tüm alanları doldurmak zorunludur.")
            return
        
        try:
            adet = float(adet_text)
            fiyat = float(fiyat_text)
        except ValueError:
            QMessageBox.critical(self, "Hata", "Adet ve fiyat sayısal olmalıdır.")
            return

        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        toplam = adet * fiyat
        rec = {
            "type": "purchase",
            "data": {
                "yem": yem, "adet": adet, "fiyat": fiyat, "toplam": toplam, "tarih": tarih
            }
        }
        self.companies[self.current_company].append(rec)
        self._update_treeview()
        self._update_total_label()

        self.entry_yem.clear()
        self.entry_adet.clear()
        self.entry_fiyat.clear()
        self._save_data()

    def _add_payment(self):
        """Ödeme kaydı ekler."""
        aciklama = self.entry_aciklama.text().strip()
        tutar_text = self.entry_tutar.text().replace(',', '.')

        if not tutar_text:
            QMessageBox.warning(self, "Uyarı", "Tutar alanı boş olamaz.")
            return
        
        try:
            tutar = float(tutar_text)
        except ValueError:
            QMessageBox.critical(self, "Hata", "Tutar sayısal olmalıdır.")
            return
        
        if not aciklama:
            aciklama = "Ödeme"
        
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rec = {
            "type": "payment",
            "data": {
                "aciklama": aciklama, "tutar": tutar, "tarih": tarih
            }
        }
        self.companies[self.current_company].append(rec)
        self._update_treeview()
        self._update_total_label()

        self.entry_aciklama.clear()
        self.entry_tutar.clear()
        self._save_data()

    def _show_context_menu(self, pos):
        """Tabloda sağ tık menüsünü gösterir."""
        if not self.tree.selectedItems():
            return
            
        menu = QMenu()
        edit_action = menu.addAction("Düzenle")
        delete_action = menu.addAction("Sil")
        
        # Seçili satırın türünü kontrol et
        selected_row = self.tree.selectedItems()[0].row()
        item_type = self.tree.item(selected_row, 0).text()
        if item_type == "Alış":
            paid_action = menu.addAction("Ödendi Yap")
        else:
            paid_action = None

        action = menu.exec_(self.tree.viewport().mapToGlobal(pos))

        if action == edit_action:
            self._edit_selected_row()
        elif action == delete_action:
            self._delete_selected_row()
        elif action == paid_action:
            self._mark_as_paid()

    def _edit_selected_row(self):
        """Seçili satırı düzenleme penceresini açar."""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Bilgi", "Düzenlemek için bir satır seçin.")
            return
        
        row = selected_items[0].row()
        
        # Internal veri kaydını bul
        record = self.companies[self.current_company][row]

        if record["type"] == "purchase":
            dialog = EditPurchaseDialog(self, record)
        elif record["type"] == "payment":
            dialog = EditPaymentDialog(self, record)
        else:
            return

        if dialog.exec_() == QDialog.Accepted:
            new_data = dialog.get_data()
            self._apply_edit(row, new_data)

    def _apply_edit(self, row, new_data):
        """Düzenleme penceresinden gelen verileri uygular."""
        # Internal data'yı güncelle
        self.companies[self.current_company][row]["data"] = new_data
        
        # Treeview'ı güncelle
        self._update_treeview()
        self._update_total_label()
        self._save_data()

    def _delete_selected_row(self):
        """Seçili satırı siler."""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Bilgi", "Silmek için bir satır seçin.")
            return

        row = selected_items[0].row()
        reply = QMessageBox.question(self, "Onay",
                                     "Seçili satırı silmek istediğinize emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.companies[self.current_company][row]
            self._update_treeview()
            self._update_total_label()
            self._save_data()

    def _mark_as_paid(self):
        """Seçili yem alışı kaydını 'Ödendi' olarak işaretler ve ödeme kaydı ekler."""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Bilgi", "Ödendi olarak işaretlemek için bir alım seçin.")
            return

        row = selected_items[0].row()
        record = self.companies[self.current_company][row]
        
        if record["type"] != "purchase":
            QMessageBox.warning(self, "Uyarı", "Bu işlem sadece yem alımları için geçerlidir.")
            return

        purchase_total = record["data"]["toplam"]
        reply = QMessageBox.question(self, "Onay",
                                     f"Bu alımı {purchase_total:.2f} TL tutarındaki bir ödemeyle kapatmak istediğinize emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rec = {
                "type": "payment",
                "data": {
                    "aciklama": "Yem alışı ödendi",
                    "tutar": purchase_total,
                    "tarih": tarih
                }
            }
            self.companies[self.current_company].append(rec)
            self._update_treeview()
            self._update_total_label()
            self._save_data()
            QMessageBox.information(self, "Başarılı", "Ödeme kaydı başarıyla eklendi.")

    # -------------------
    # Yardımcı Fonksiyonlar
    # -------------------
    def _sort_treeview(self, column, order):
        """Tabloyu tıklanan sütuna göre sıralar."""
        self._sort_column = column
        self._sort_order = order
        
        def get_value(record):
            data = record["data"]
            if column == 0:  # Tür
                return record["type"]
            elif column == 1: # Açıklama / Yem Adı
                return data.get("yem", data.get("aciklama"))
            elif column == 2: # Adet
                return data.get("adet", 0)
            elif column == 3: # Birim Fiyat
                return data.get("fiyat", 0)
            elif column == 4: # Toplam
                return data.get("toplam", -data.get("tutar", 0))
            elif column == 5: # Tarih
                return datetime.strptime(data.get("tarih"), "%Y-%m-%d %H:%M:%S")

        current_records = self.companies.get(self.current_company, [])
        try:
            sorted_records = sorted(current_records, key=get_value, reverse=(order == Qt.DescendingOrder))
            self.companies[self.current_company] = sorted_records
            self._update_treeview()
        except Exception as e:
            QMessageBox.critical(self, "Sıralama Hatası", f"Veri sıralanırken bir hata oluştu: {e}")

    # -------------------
    # Veri Saklama (JSON)
    # -------------------
    def _load_data(self):
        """data.json dosyasından veriyi yükler."""
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            
            if isinstance(d, dict):
                # Veri formatını kontrol et ve gerekirse dönüştür
                for company, records in d.items():
                    new_records = []
                    for rec in records:
                        if "type" not in rec:
                            new_records.append({
                                "type": "purchase",
                                "data": rec
                            })
                        else:
                            new_records.append(rec)
                    self.companies[company] = new_records
            
                self._update_company_list()
            else:
                print("Beklenmeyen data.json formatı. Yoksayılıyor.", file=sys.stderr)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri yüklenemedi: {e}")

    def _save_data(self):
        """Tüm şirket verilerini data.json'a kaydeder."""
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.companies, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri kaydedilemedi: {e}")
            
    def closeEvent(self, event):
        """Pencere kapanırken veriyi kaydeder."""
        self._save_data()
        event.accept()

    def get_float_validator(self):
        """Kayan nokta sayıları için bir doğrulayıcı oluşturur."""
        validator = QDoubleValidator(0.00, 99999999.00, 2)
        validator.setNotation(QDoubleValidator.StandardNotation)
        return validator

# ---------------------------
# Satır Düzenleme Penceresi - Alış
# ---------------------------
class EditPurchaseDialog(QDialog):
    def __init__(self, parent, old_record):
        super().__init__(parent)
        self.setWindowTitle("Yem Alışını Düzenle")
        self.old_data = old_record["data"]
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        form_layout = QHBoxLayout()
        
        form_layout.addWidget(QLabel("Yem Adı:"))
        self.e_yem = QLineEdit()
        self.e_yem.setText(self.old_data["yem"])
        form_layout.addWidget(self.e_yem)
        
        form_layout.addWidget(QLabel("Adet:"))
        self.e_adet = QLineEdit()
        self.e_adet.setText(str(self.old_data["adet"]))
        self.e_adet.setValidator(self.parent().get_float_validator())
        form_layout.addWidget(self.e_adet)
        
        form_layout.addWidget(QLabel("Birim Fiyat:"))
        self.e_fiyat = QLineEdit()
        self.e_fiyat.setText(str(self.old_data["fiyat"]))
        self.e_fiyat.setValidator(self.parent().get_float_validator())
        form_layout.addWidget(self.e_fiyat)
        
        layout.addLayout(form_layout)
        
        layout.addWidget(QLabel(f"Tarih: {self.old_data['tarih']}"))

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
        self.setLayout(layout)

    def get_data(self):
        """Düzenlenmiş veriyi döner."""
        yem = self.e_yem.text().strip()
        adet = float(self.e_adet.text().replace(',', '.'))
        fiyat = float(self.e_fiyat.text().replace(',', '.'))
        
        return {
            "yem": yem,
            "adet": adet,
            "fiyat": fiyat,
            "toplam": adet * fiyat,
            "tarih": self.old_data["tarih"]
        }

# ---------------------------
# Satır Düzenleme Penceresi - Ödeme
# ---------------------------
class EditPaymentDialog(QDialog):
    def __init__(self, parent, old_record):
        super().__init__(parent)
        self.setWindowTitle("Ödemeyi Düzenle")
        self.old_data = old_record["data"]
        self.setModal(True)
        self._build_ui()
        
    def _build_ui(self):
        layout = QVBoxLayout()
        form_layout = QHBoxLayout()
        
        form_layout.addWidget(QLabel("Açıklama:"))
        self.e_aciklama = QLineEdit()
        self.e_aciklama.setText(self.old_data["aciklama"])
        form_layout.addWidget(self.e_aciklama)
        
        form_layout.addWidget(QLabel("Tutar:"))
        self.e_tutar = QLineEdit()
        self.e_tutar.setText(str(self.old_data["tutar"]))
        self.e_tutar.setValidator(self.parent().get_float_validator())
        form_layout.addWidget(self.e_tutar)

        layout.addLayout(form_layout)
        
        layout.addWidget(QLabel(f"Tarih: {self.old_data['tarih']}"))

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
        self.setLayout(layout)

    def get_data(self):
        """Düzenlenmiş veriyi döner."""
        aciklama = self.e_aciklama.text().strip()
        tutar = float(self.e_tutar.text().replace(',', '.'))
        
        if not aciklama:
            aciklama = "Ödeme"
            
        return {
            "aciklama": aciklama,
            "tutar": tutar,
            "tarih": self.old_data["tarih"]
        }

# ---------------------------
# Uygulamayı Başlatma
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Stylesheet kullanarak modern bir görünüm kazandırın
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QListWidget {
            border: 1px solid #c0c0c0;
            border-radius: 5px;
            padding: 5px;
            background-color: white;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QLineEdit, QTableWidget {
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            padding: 5px;
        }
        QTableWidget::item {
            padding: 5px;
        }
        QLabel {
            font-family: Arial;
        }
    """)
    
    main_window = CariApp()
    main_window.show()
    sys.exit(app.exec_())

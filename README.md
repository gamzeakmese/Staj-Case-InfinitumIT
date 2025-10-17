# 🚀URL Downloader

Dosyaları eş zamanlı indirme ve progress tracking sağlayan web uygulaması.

## Kurulum

### Backend
```bash
pip install -r requirements.txt
python backend.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Kullanım

1. Backend'i başlat: `python backend.py`
2. Frontend'i başlat: `npm run dev`
3. Tarayıcıda aç: `http://localhost:3000`
4. "İndirmeyi Başlat" butonuna tıkla

## Notlar

- İndirilen dosyalar `downloads/` klasörüne kaydedilir.
- Downloads klasörü backend başlatıldığında otomatik oluşturulur.
- Dosyalar `.tmp` uzantısıyla kaydedilir.
- Raporlar otomatik olarak oluşturulur ve hem dosyaya kaydedilir hem konsola yazdırılır.
- JSON raporları okunabilir formatta konsola yazdırılır.
# Aplikasi Kalibrasi & Pengukuran Dimensi

Web app Python (Streamlit) yang mereplikasi perhitungan pada file Excel
`Proyek_Pengukuran_Teknik_Seher_Vixion_NVL.xlsx`: kalibrasi alat ukur terhadap
gauge block (sheet **General**) dan statistik pengukuran berulang per anggota
+ keseluruhan (sheet **Pengukuran**) — Mean, Median, Range, Std Dev, CV,
Systematic Error, SEM, Combined Error, Expanded Uncertainty (k=2), Confidence
Interval 95%, dan Final Result.

## Cara menjalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

Browser akan otomatis terbuka di `http://localhost:8501`.

## Cara pakai

1. Isi info proyek & **Ukuran Acuan** di sidebar.
2. Isi tabel kalibrasi gauge block (bisa tambah/hapus baris) — systematic
   error otomatis dihitung lewat interpolasi linear.
3. Isi tabel pengukuran per anggota (bisa tambah anggota / ubah jumlah
   pengulangan pengukuran).
4. Hasil per anggota dan ringkasan keseluruhan tampil otomatis, lengkap
   dengan tombol **Download Hasil (Excel)**.

# Laptambemas
Aplikasi web laporan keuangan proyek dalam bahasa Indonesia. Dashboard mengikuti referensi warna cokelat, kartu ringkasan, dan pemilihan proyek. Mendukung arus kas, hutang/piutang dengan pelunasan, aset, filter bulan, ekspor CSV, serta akun tim. Tampilan responsif untuk ponsel.

## Menjalankan
Memerlukan Python 3.12+, tanpa dependency tambahan.

```sh
cd /workspace/laptambemas
python3 server.py
```
Buka server pada port 8000. Saat pertama digunakan, buat akun admin melalui halaman awal. Admin menambahkan akun anggota di menu Tim. Semua pengguna berbagi database yang sama dan dapat menambah catatan di semua proyek. Tidak ada akun atau password bawaan.

Database SQLite tersimpan di `.data/finance.sqlite3`, bukan di Git. `DATA_DIR` dapat diarahkan ke volume persisten. Backup database dengan SQLite backup API saat aplikasi berjalan; simpan backup di lokasi aman. Proses dan database pada mesin berbeda tidak otomatis tersinkronisasi.

## Perhitungan
- Saldo kas = seluruh uang masuk dikurangi seluruh uang keluar per proyek.
- Filter bulan berlaku untuk transaksi dan daftar laporan. Kartu saldo, hutang/piutang belum lunas, dan nilai aset menampilkan posisi seluruh periode.
- Hutang/piutang adalah daftar kewajiban/tagihan, bukan otomatis transaksi kas. Penerimaan pinjaman dicatat juga sebagai uang masuk. Pelunasan penuh otomatis menambah transaksi kas, hanya sekali.
- Aset menggunakan nilai perolehan; pembelian aset dicatat juga sebagai uang keluar. Penyusutan, penjualan aset, pembayaran sebagian, dan pembukuan akuntansi lengkap belum tersedia.
- Catatan bersifat tambah saja, tanpa hapus/edit. Periksa data sebelum menyimpan.

## Pengujian
```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

## Akses internet untuk tim
Versi ini berjalan di server lokal cloud, belum dipublikasikan sebagai situs internet. Untuk produksi gunakan hosting Python dengan volume SQLite persisten, satu instance, HTTPS reverse proxy dan `HOST=0.0.0.0 COOKIE_SECURE=1`. PORT default 8000. Buat admin pertama sebelum membuka akses publik. Dibutuhkan hardening lanjutan seperti pembatasan percobaan login, reset password, manajemen pencabutan anggota, backup terjadwal, dan audit perubahan sebelum penggunaan luas. Jangan masukkan password atau database ke Git. Aplikasi tidak mengirim pesan WhatsApp atau terhubung ke Firebase.

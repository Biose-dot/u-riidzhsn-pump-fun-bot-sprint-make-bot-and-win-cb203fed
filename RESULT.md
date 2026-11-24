# Breakout Rider — build result

Bot paper-trading pump.fun ("Breakout Rider") untuk bounty
[Pump.fun Bot Sprint: Make Bot And Win](https://make.fun/c/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed).

## Strategi

Bot beli hanya saat breakout: harga menembus high 60-slot terakhir dengan
aliran beli yang luas dan menguat (beberapa buyer berbeda, buy mendominasi
tape, net SOL masuk, inflow paruh kedua ≥ paruh pertama), plus filter
anti-bundle (tidak ada satu buyer yang mendominasi). Ukuran beli 0,05 SOL
(0,08 SOL saat inflow sangat kuat), maks 5 posisi terbuka, maks 2 entry per
kurva. Exit: partial take-profit +35% (jual separuh), take-profit penuh +90%,
stop-loss −12%, trailing stop −18% dari peak (arm saat +15%), exit saat tape
berbalik seller-dominated, dan batas hold 1200 slot. Deterministik penuh
(stdlib Python saja, tanpa clock/random/network).

## Verifikasi lokal

`python3 main.py` dijalankan terhadap replay seluruh event nyata dari dataset
kit (dev window, 128.058 event / 1.222 kurva) via mini-harness lokal:
berjalan tanpa error, output dua run identik byte-for-byte (determinisme
terpenuhi), 258 buy + 281 sell di 147 koin berbeda (jauh di atas guardrail
min. 20 koin), 0 order ditolak. Kas akhir simulasi lokal ~9,32 SOL dari
10 SOL — angka ini hanya indikatif karena mini-harness memakai model fill
sendiri, bukan scorer resmi; yang terverifikasi adalah bot berdagang luas,
deterministik, dan patuh pada semua cap harness.

## Status: built, pending coordinator bundle+submit

Repo sudah di-push ke GitHub; bundle/submit/status dilakukan koordinator.
Kit: `~/workspace/makefun/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed-kit/`

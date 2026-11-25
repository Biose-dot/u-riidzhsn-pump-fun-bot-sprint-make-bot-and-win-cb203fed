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

## Status: SUBMITTED + VERIFIED

- Submission ID: 01a210a4-d0ae-76de-b873-35747d882262
- Bundle: u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed-bundle.tar.gz (sha256 bee1ab59...)
- Submitted: 2026-11-25 ~09:59 WIB (batch 0516 grup F finisher; kit segar level 45; check 15 pass, reproduces 90.3%)
- Status: all checks PASS server-side; round 1 passed every validity check; grading dev phase under way. Entries close 28 Nov 15:00 WIB; result due 12 Dec 2026.

## Status: built, pending coordinator bundle+submit

Repo sudah di-push ke GitHub; bundle/submit/status dilakukan koordinator.
Kit: `~/workspace/makefun/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed-kit/`

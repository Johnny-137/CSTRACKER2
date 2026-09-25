# 🎮 CS2 Inventory Tracker

Osobní web pro sledování cen CS2 skinů s automatickou aktualizací každý den.

## Co tento projekt dělá

- Každý den v 8:00 UTC automaticky stáhne tvůj CS2 inventář
- Zjistí aktuální tržní ceny ze Steam Market (bez placených API klíčů)
- Ukládá historii cen a zobrazuje grafy vývoje
- Umožňuje zadat nákupní ceny a vidět zisk/ztrátu

## Struktura souborů

```
├── index.html                  ← Webová stránka (to co vidíš v prohlížeči)
├── fetch_inventory.py          ← Python skript pro stahování dat
├── data/
│   ├── purchase_prices.json    ← ⭐ SEM doplňuješ své nákupní ceny!
│   ├── history.json            ← Automaticky generovaná historie (nesahej na to)
│   └── summary.json            ← Automaticky generovaný souhrn (nesahej na to)
└── .github/
    └── workflows/
        └── update-inventory.yml ← Nastavení automatického spouštění
```

## Jak zadat nákupní ceny

Otevři soubor `data/purchase_prices.json` a doplň ceny ve formátu:

```json
{
  "Přesný název předmětu (Opotřebení)": 12.50,
  "AK-47 | Redline (Field-Tested)": 8.50
}
```

**Kde zjistit přesný název?** Po prvním spuštění skriptu otevři soubor `data/summary.json` – tam jsou všechny názvy přesně tak, jak je potřebuješ.

## Licence

Volně použitelné pro osobní účely.

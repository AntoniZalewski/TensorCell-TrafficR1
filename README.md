# Traffic-R1: LLM-driven Traffic Signal Control 🚦

Dokumentacja techniczna i instrukcja uruchomienia środowiska symulacyjnego Traffic-R1. Projekt integruje symulator CityFlow z modelem językowym Qwen 2.5 (Traffic-R1) w celu optymalizacji sterowania ruchem miejskim.

## 🛠️ Wymagania Systemowe

1.  **Docker Desktop**: Musi być zainstalowany i **uruchomiony** w tle.
2.  **GPU NVIDIA**: Wymagana karta graficzna z obsługą CUDA.
3.  **Model**: Pliki modelu Traffic-R1 muszą znajdować się w lokalizacji `models/Traffic-R1/huggingface`.

## 🚀 Instrukcja Uruchomienia (Docker)

Całe środowisko zostało skonteneryzowane, aby uniknąć problemów z zależnościami na Windows/Linux.

### 1. Budowanie Obrazu
Wykonaj to polecenie raz, aby zbudować środowisko. Docker automatycznie pobierze i zainstaluje wszystkie wymagane biblioteki z pliku `requirements.txt` (m.in. `transformers`, `peft`, `cityflow`).

```bash
docker build -t traffic-r1-env .
```

### 2. Start Kontenera
Uruchomienie interaktywnej sesji z montowaniem bieżącego katalogu (dzięki temu wyniki zapisują się na dysku hosta).

**Windows (PowerShell):**
```powershell
docker run --gpus all -it --rm -v ${PWD}:/app -e WANDB_MODE=disabled traffic-r1-env
```

**Linux / macOS / WSL:**
```bash
docker run --gpus all -it --rm -v $(pwd):/app -e WANDB_MODE=disabled traffic-r1-env
```

> **Uwaga:** Jeśli otrzymasz błąd `error during connect`, upewnij się, że aplikacja Docker Desktop jest włączona.

### 3. Uruchomienie Symulacji
Po wejściu do kontenera (prompt zmieni się na `root@...:/app#`), uruchom symulację poleceniem:

```bash
python scripts/run_open_LLM.py \
  --dataset jinan \
  --traffic_file anon_3_4_jinan_real.json \
  --num_rounds 1 \
  --llm_path /app/models/Traffic-R1/huggingface \
  --llm_model Traffic-R1
```

## 📊 Analiza Wyników

Po zakończeniu symulacji wyniki znajdują się w katalogu `records/`.
Nowa struktura folderów to: `records/<Model>_<Miasto>_<Data>_<Godzina>/`.

*   **Metryki:** Plik `advanced_metrics.json` wewnątrz folderu z wynikami.
*   **Wizualizacja (Ułatwiona):**
    1.  Otwórz `frontend/index.html` w przeglądarce.
    2.  Wybierz plik mapy: `data/jinan/roadnet_3_4.json`.
    3.  Wybierz plik logu: **`frontend/latest_replay.txt`** (to automatyczny skrót do najnowszego wyniku!).

> [!NOTE]
> **Generowanie Video:** Funkcjonalność automatycznego generowania wizualizacji video jest obecnie w fazie rozwoju (work in progress).

## 📂 Struktura Repozytorium

*   `run_open_LLM.py` – Główny skrypt startowy.
*   `utils/metrics.py` – Moduł analityczny (TrafficMetrics).
*   `models/` – Katalog na wagi modeli.
*   `data/` – Dane wejściowe (mapy, scenariusze ruchu).
*   `records/` – Logi i wyniki symulacji.

import json
import numpy as np
import os

class TrafficMetrics:
    def __init__(self):
        # Słownik aktywnych pojazdów: {vehicle_id: {enter_time, waiting_time}}
        self.active_vehicles = {}
        # Lista zakończonych podróży
        self.completed_trips = []
        
        # Globalne liczniki dla wszystkich pojazdów (również tych, które nie dojechały)
        self.total_waiting_time_all_steps = 0
        self.total_waiting_time_incoming_lanes = 0

    def update(self, engine, current_time):
        # Pobierz listę pojazdów w tej sekundzie
        vehicles = engine.get_vehicles()
        vehicle_speeds = engine.get_vehicle_speed()
        
        # 1. Rejestracja nowych i aktualizacja aktywnych
        current_ids = set(vehicles)
        for vid in current_ids:
            if vid not in self.active_vehicles:
                self.active_vehicles[vid] = {
                    "enter_time": current_time,
                    "waiting_time": 0
                }
            
            # Aktualizacja waiting time (jeśli prędkość < 0.1 m/s)
            speed = vehicle_speeds.get(vid, 0)
            if speed < 0.1:
                self.active_vehicles[vid]["waiting_time"] += 1
                self.total_waiting_time_all_steps += 1
                # Tu można dodać logikę dla 'incoming lanes' jeśli mamy ID pasów, 
                # na razie zakładamy uproszczenie: waiting na skrzyżowaniu = incoming
                self.total_waiting_time_incoming_lanes += 1

        # 2. Wykrywanie pojazdów, które zakończyły trasę (zniknęły z silnika)
        active_ids = list(self.active_vehicles.keys())
        for vid in active_ids:
            if vid not in current_ids:
                # Pojazd zakończył podróż
                data = self.active_vehicles.pop(vid)
                real_time = current_time - data["enter_time"]
                waiting_time = data["waiting_time"]
                
                # Ideal time = Czas rzeczywisty - Czas stania w korku
                # (To uproszczenie, ale standardowe w RL bez mapy topologicznej)
                ideal_time = max(1, real_time - waiting_time) 
                
                self.completed_trips.append({
                    "id": vid,
                    "real_time": real_time,
                    "ideal_time": ideal_time,
                    "delay": waiting_time # Delay definiujemy jako czas stracony
                })

    def save_summary(self, output_path):
        if not self.completed_trips:
            print("Warning: No vehicles completed their journey.")
            return

        # Obliczenia Numpy dla wydajności
        delays = [t["delay"] for t in self.completed_trips]
        real_times = [t["real_time"] for t in self.completed_trips]
        ideal_times = [t["ideal_time"] for t in self.completed_trips]

        # 1. Count_of_vehicles_completing_journey
        count_finished = len(self.completed_trips)

        # 2. Total_sum_delays_of_all_vehicles_from_all_routes
        sum_delays = sum(delays)

        # 3. Total_average_delays_of_all_vehicles_from_all_routes
        avg_delays = sum_delays / count_finished if count_finished > 0 else 0

        # 4. Total_time_of_journey
        total_journey_time = sum(real_times)

        # 5. Average_time_of_journey
        avg_journey_time = total_journey_time / count_finished if count_finished > 0 else 0

        # 6. Total_average_delays_real_times_by_ideal_times
        sum_ideal = sum(ideal_times)
        ratio_real_ideal = (sum(real_times) / sum_ideal) if sum_ideal > 0 else 0

        # 7 & 8. Global waiting times (liczone w update)
        
        metrics = {
            "Count_of_vehicles_completing_journey": count_finished,
            "Total_sum_delays_of_all_vehicles_from_all_routes": float(sum_delays),
            "Total_average_delays_of_all_vehicles_from_all_routes": float(avg_delays),
            "Total_time_of_journey": float(total_journey_time),
            "Average_time_of_journey": float(avg_journey_time),
            "Total_average_delays_real_times_by_ideal_times": float(ratio_real_ideal),
            "Total_waiting_time_all_vehicles_in_simulation_in_episode": self.total_waiting_time_all_steps,
            "Total_waiting_time_on_the_incoming_lanes_in_episode": self.total_waiting_time_incoming_lanes
        }

        # Zapis do pliku
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=4)
        
        print(f"\n[METRICS] Saved comprehensive report to: {output_path}")
        print(f"[METRICS] Completed Journeys: {count_finished}")
        print(f"[METRICS] Avg Delay: {avg_delays:.2f}s")

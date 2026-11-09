import simpy
import random
import matplotlib.pyplot as plt

def compute_fraction_ships_diverted(sim, ship_type):
    # Pattern: Reporting - slides 14-15
    # Turns the quoted/diverted counters filled in ship() into a percentage.
    if ship_type == 'feeder':
        return f"{sim.nr_diverted_ships_F * 100 / sim.nr_quoted_ships_F:.2f}%"
    elif ship_type == 'deepsea':
        return f"{sim.nr_diverted_ships_D * 100 / sim.nr_quoted_ships_D:.2f}%"
    elif ship_type == 'all':
        return f"{(sim.nr_diverted_ships_F + sim.nr_diverted_ships_D) * 100 / (sim.nr_quoted_ships_F + sim.nr_quoted_ships_D):.2f}%"
    else:
        return f"SHIP TYPE DOES NOT EXIST!"


def compute_team_restacking_time(sim, team):
    # Pattern: Reporting - slides 14-15
    # Returns the restacking hours tracked per team inside ship().
    if team == 'alpha':
        return sim.restacking_hours_alpha
    elif team == 'bravo':
        return sim.restacking_hours_bravo
    elif team == 'charlie':
        return sim.restacking_hours_charlie
    else:
        return f"TEAM DOES NOT EXIST!"


def compute_average_turnaround_time(turnaround_points, ship_type="all", start_hour=0.0, end_hour=None):
    # Pattern: Reporting + Warmup time - slides 14-15, 18
    # Averages the recorded turnaround times; start_hour/end_hour let early (warm-up) ships be excluded.
    hour_d = 0; hour_f = 0
    d_count = 0; f_count = 0
    for time, hour, type in turnaround_points:
        if time < start_hour or (end_hour is not None and time >= end_hour):
            continue
        if type == 'feeder': 
            hour_f += hour
            f_count += 1
        elif type == 'deep-sea':
            hour_d += hour
            d_count += 1
    if ship_type == 'feeder': 
        return hour_f / f_count
    elif ship_type == 'deepsea':
        return hour_d / d_count
    elif ship_type == 'all':
        return (hour_f + hour_d) / (f_count + d_count)


def plot_turnaround_times(turnaround_points, start_hour=0.0, end_hour=None):
    # Pattern: Reporting - slides 14-15, 18
    # Plots turnaround time against announcement time, like the line plot of slide 18.
    hour_f=[]; arrival_f=[]
    hour_d=[]; arrival_d=[]
    hour_a=[]; arrival_a=[]

    for time, hour, type in turnaround_points:
        if time < start_hour or (end_hour is not None and time >= end_hour):
            continue
        if type == 'feeder': 
            hour_f.append(hour)
            arrival_f.append(time)
            hour_a.append(hour)
            arrival_a.append(time)
        elif type == 'deep-sea':
            hour_d.append(hour)
            arrival_d.append(time)
            hour_a.append(hour)
            arrival_a.append(time)

    plt.figure(figsize=(10, 6))
    plt.grid(True)
    plt.plot(arrival_f, hour_f, label = "Feeder ships")
    plt.plot(arrival_d, hour_d, label = "Deep-sea ships")
    plt.plot(arrival_a, hour_a, label = "All ships")
    plt.xlabel("Announcement moment of the ship (hours)")
    plt.ylabel("Turnaround time (hours)")
    plt.title("Development of the turnaround times")
    plt.legend()

    print(f"Average turnaround time for feeder ships: {sum(hour_f) /  len(hour_f):.2f}")
    print(f"Average turnaround time for deep-sea ships: {sum(hour_d) /  len(hour_d):.2f}")
    print(f"Average turnaround time for all ships: {sum(hour_a) /  len(hour_a):.2f}")

    plt.show()


class ContainerTerminalSimulator:
    """A SimPy simulation model for a container terminal handling ships."""

    def __init__(self):
        # Counters required by the checker
        self.nr_arrived_ships_F = 0  # Count of all announced feeder ships.
        self.nr_arrived_ships_D = 0  # Count of all announced deep-sea ships.
        self.nr_quoted_ships_F = 0  # Count of fee quotations sent for feeder ships.
        self.nr_quoted_ships_D = 0  # Count of fee quotations sent for deep-sea ships.
        self.sum_fees_F = 0.0  # Sum of all handling fees quoted for feeder ships.
        self.sum_fees_D = 0.0  # Sum of all handling fees quoted for deep-sea ships.
        self.nr_fees_F_above = 0  # Count of feeder fees above the limit.
        self.nr_fees_D_above = 0  # Count of deep-sea fees above the limit.
        self.nr_diverted_ships_F = 0  # Count of feeder ships sent to another terminal.
        self.nr_diverted_ships_D = 0  # Count of deep-sea ships sent to another terminal.
        self.nr_towed_ships_F = 0  # Count of feeder ships that needed a tugboat.
        self.nr_towed_ships_D = 0  # Count of deep-sea ships that needed a tugboat.
        self.nr_docked_ships_F = 0  # Count of feeder ships docked at the quay.
        self.nr_docked_ships_D = 0  # Count of deep-sea ships docked at the quay.
        self.nr_unloaded_ships_F = 0  # Count of feeder ships fully unloaded.
        self.nr_unloaded_ships_D = 0  # Count of deep-sea ships fully unloaded.
        self.unloading_by_alpha = 0  # Count of ships unloaded by team alpha.
        self.unloading_by_bravo = 0  # Count of ships unloaded by team bravo.
        self.unloading_by_charlie = 0  # Count of ships unloaded by team charlie.
        self.nr_restacked_ships = 0  # Count of unloadings that needed restacking.
        self.restacking_by_alpha = 0  # Count of restacking jobs done by team alpha.
        self.restacking_by_bravo = 0  # Count of restacking jobs done by team bravo.
        self.restacking_by_charlie = 0  # Count of restacking jobs done by team charlie.
        self.nr_scanned_ships_F = 0  # Count of feeder ships cleared by customs.
        self.nr_scanned_ships_D = 0  # Count of deep-sea ships cleared by customs.
        self.nr_minor_problem = 0  # Count of scans with a minor problem.
        self.nr_major_problem = 0  # Count of scans with a major problem.
        self.nr_delivered_loads_F = 0  # Count of feeder loads delivered inland by barge.
        self.nr_delivered_loads_D = 0  # Count of deep-sea loads delivered inland by barge.
        self.restacking_hours_alpha = 0.0  # Hours team alpha spent on restacking.
        self.restacking_hours_bravo = 0.0  # Hours team bravo spent on restacking.
        self.restacking_hours_charlie = 0.0  # Hours team charlie spent on restacking.
        # Turnaround series: list of (announcement_time, turnaround_hours, ship_type)
        self.turnaround_points = []

    # ---------------------------------- Simulation -----------------------------------

    # Pattern: Customer Generator + Choice - slides 8, 10, 25
    # Endless loop: create a ship, wait an exponential inter-arrival time; a draw picks feeder (65%) or deep-sea (35%).
    def ship_generator(self, env):
            while True:
                yield env.timeout(random.expovariate(8 / 168))
                if random.random() <= 0.65:
                    ship_type = 'feeder'
                else:
                    ship_type = 'deep-sea'
                env.process(self.ship(env, ship_type))
    
    # Pattern: Events (timer) - slides 5, 27; Resources with limited availability - slide 30 
    # Opening hours: returns how long to wait until the terminal opens; callers yield it as a timeout.
    def get_wait_until_open(self, current_time):
            week_hr = current_time % 168
            if week_hr < 6: return 6 - week_hr      
            elif week_hr < 22: return 0                 
            elif week_hr < 30: return 30 - week_hr      
            elif week_hr < 46: return 0                 
            elif week_hr < 54: return 54 - week_hr      
            elif week_hr < 70: return 0                 
            elif week_hr < 78: return 78 - week_hr      
            elif week_hr < 94: return 0                
            elif week_hr < 102: return 102 - week_hr   
            elif week_hr < 118: return 0                
            elif week_hr < 126: return 126 - week_hr    
            elif week_hr < 142: return 0                
            else: return 168 - week_hr + 6              

    # Pattern: Process + Sequence - slides 7-8, 23
    # One ship is one process; tasks 1-5 follow each other in sequence.
    def ship(self, env, ship_type):
        announce_time = env.now
        confirm_time = announce_time + 120
        # Task 1 - Pattern: Sequence + Choice - slides 23, 24-25
        # The 5-day booking is a timer event; after the quotation a Choice decides if the ship is diverted.
        if ship_type == 'feeder':
            self.nr_arrived_ships_F += 1
            yield env.timeout(120)
            fee = random.uniform(4000, 12000)
            self.nr_quoted_ships_F += 1
            self.sum_fees_F += fee
            if fee > 9000:
                self.nr_fees_F_above += 1
                if random.random() < 0.30:
                    self.nr_diverted_ships_F += 1
                    return
            # Task 2 - Pattern: Choice - slides 24-25
            # Only 30% of feeders are towed; otherwise the task is skipped. Tugboats are unlimited, so no resource.
            if random.random() < 0.3:
                self.nr_towed_ships_F += 1
                yield env.timeout(6)
            self.nr_docked_ships_F += 1
        # Task 1 (deep-sea) - Pattern: Different case types - slide 30
        # Same Sequence + Choice as for feeders, with the deep-sea fee range and diversion limit.
        elif ship_type == 'deep-sea':
            self.nr_arrived_ships_D += 1
            yield env.timeout(120)
            fee = random.uniform(25000, 60000)
            self.nr_quoted_ships_D += 1
            self.sum_fees_D += fee
            if fee > 50000:
                self.nr_fees_D_above += 1
                if random.random() < 0.1:
                    self.nr_diverted_ships_D += 1
                    return
            # Task 2 (deep-sea) - Pattern: Sequence (timer event) - slides 23, 10
            # Always towed; the exponential time is a plain timeout.
            self.nr_towed_ships_D += 1
            yield env.timeout(random.expovariate(1 / 18))
            self.nr_docked_ships_D += 1
        # Task 3 - Pattern: Choice + Multiple resources - slides 25, 29 (Resource: slide 10)
        # One draw selects the team (40/35/25%). Each team is its own Resource: request, wait, unload, release.
        draw = random.random()
        if draw < 0.4:
            team = self.team_alpha.request()
            yield team
            yield env.timeout(self.get_wait_until_open(env.now))
            yield env.timeout(8)
            self.unloading_by_alpha += 1
            self.team_alpha.release(team)
        elif draw < 0.75:
            team = self.team_bravo.request()
            yield team
            yield env.timeout(self.get_wait_until_open(env.now))
            yield env.timeout(11)
            self.unloading_by_bravo += 1
            self.team_bravo.release(team)
        else:
            team = self.team_charlie.request()
            yield team
            yield env.timeout(self.get_wait_until_open(env.now))
            yield env.timeout(16)
            self.unloading_by_charlie += 1
            # Restacking - Pattern: Choice (nested) + Multiple resources - slides 24-25, 29
            # Charlie keeps its resource (20%) or releases it and requests team alpha or bravo.
            if random.random() < 0.25:
                if random.random() < 0.2:
                    yield team
                    yield env.timeout(2)
                    self.restacking_hours_charlie += 2
                    self.restacking_by_charlie += 1
                    self.team_charlie.release(team)
                else:
                    self.team_charlie.release(team)
                    if random.random() < 0.5:
                        team = self.team_alpha.request()
                        yield team
                        yield env.timeout(2)
                        self.restacking_hours_alpha += 2
                        self.restacking_by_alpha += 1
                        self.team_alpha.release(team)
                    else:
                        team = self.team_bravo.request()
                        yield team
                        yield env.timeout(2)
                        self.restacking_hours_bravo += 2
                        self.restacking_by_bravo += 1
                        self.team_bravo.release(team)
                self.nr_restacked_ships += 1
            else:
                self.team_charlie.release(team)
        if ship_type == 'feeder':
            self.nr_unloaded_ships_F += 1
        else:
            self.nr_unloaded_ships_D += 1
        # Task 4 - Pattern: Resource - slide 10
        # Customs is a Resource (capacity 1): request, wait for opening hours, scan 4 h, release after any problem.
        cus = self.customs.request()
        yield cus
        yield env.timeout(self.get_wait_until_open(env.now))
        yield env.timeout(4)
        # Pattern: Choice - slide 25
        # One draw: 8% minor problem, 2% major problem (needs team alpha as a second resource), else none.
        dr = random.random()
        if dr < 0.08:
            yield env.timeout(1)
            self.nr_minor_problem += 1
        elif dr < 0.1:
            team = self.team_alpha.request()
            yield team
            yield env.timeout(4)
            self.team_alpha.release(team)
            self.nr_major_problem += 1
        self.customs.release(cus)
        if ship_type == 'feeder':
            self.nr_scanned_ships_F += 1
        else:
            self.nr_scanned_ships_D += 1
        # Task 5 - Pattern: Sequence with timer events - slides 23, 27
        # Wait for the next 18:00 barge (not on Sunday), then sail 5-9 h. Barges are unlimited, so no resource.
        day = int(env.now // 24) % 7
        hour = env.now % 24
        if hour <= 18:
            wait = 18 - hour
            departure_day = day
        else:
            wait = 24 + 18 - hour
            departure_day = (day + 1) % 7
        if departure_day == 6:
            wait += 24
        yield env.timeout(random.uniform(5, 9) + wait)
        if ship_type == 'feeder':
            self.nr_delivered_loads_F += 1
        else:
            self.nr_delivered_loads_D += 1
        # Pattern: Reporting - slides 14-15
        # After the last step of the sequence, record (announcement time, turnaround time, kind).
        self.turnaround_points.append((announce_time, env.now - confirm_time, ship_type))

    def simulate(self, duration):
        """Simulation function without random seed."""
        env = simpy.Environment()
        # Simulation set-up - Pattern: Multiple resources - slides 11, 29
        # One Resource per crane team and for customs; the generator process is started and run.
        self.team_alpha = simpy.Resource(env, capacity = 1)
        self.team_bravo = simpy.Resource(env, capacity = 1)
        self.team_charlie = simpy.Resource(env, capacity = 1)
        self.customs = simpy.Resource(env, capacity = 1)
        env.process(self.ship_generator(env))
        env.run(duration)
        return env


# -------------------------------------------------------------------------------------
# --------------------------- SOLUTION CHECK (Don't change) ---------------------------
# -------------------------------------------------------------------------------------
if __name__ == "__main__":
    print(
        "\n\nDISCLAIMER\nIf you do not see DONE, this means that the program got stuck somewhere and consequently does not work properly. "
        + "Finally, note that you must use all attributes and functions that are defined in the template and give them correct values according to the assignment description. "
        + "You must not change names or signatures of predefined classes, attributes or functions. Doing so may lead to severe deduction of points. "
        + "\n\nRESULTS"
    )
    Terminal = ContainerTerminalSimulator()
    simulation = Terminal.simulate(8760)  # 1 year = 8760 hours
    total_ships = Terminal.nr_arrived_ships_F + Terminal.nr_arrived_ships_D
    total_unloaded = (
        Terminal.nr_unloaded_ships_F + Terminal.nr_unloaded_ships_D
    )
    total_scanned = Terminal.nr_scanned_ships_F + Terminal.nr_scanned_ships_D
    total_confirmed_ships = (
        Terminal.nr_quoted_ships_F
        + Terminal.nr_quoted_ships_D
        - Terminal.nr_diverted_ships_F
        - Terminal.nr_diverted_ships_D
    )
    total_delivered = (
        Terminal.nr_delivered_loads_F + Terminal.nr_delivered_loads_D
    )
    weeks = 8760 / 168
    avg_turnaround_F = compute_average_turnaround_time(
        Terminal.turnaround_points, "feeder"
    )
    avg_turnaround_D = compute_average_turnaround_time(
        Terminal.turnaround_points, "deepsea"
    )
    avg_turnaround_all = compute_average_turnaround_time(
        Terminal.turnaround_points, "all"
    )
    print("Simulation Duration:", simulation.peek())
    print("Total Feeder Ships Announced:", Terminal.nr_arrived_ships_F)
    print("Total Deep-Sea Ships Announced:", Terminal.nr_arrived_ships_D)
    print(
        f"Feeder Ships with a Fee Quote: {Terminal.nr_quoted_ships_F}, avg: EUR {Terminal.sum_fees_F / Terminal.nr_quoted_ships_F if Terminal.nr_quoted_ships_F else 0:.1f}"
    )
    print(
        f"Deep-Sea Ships with a Fee Quote: {Terminal.nr_quoted_ships_D}, avg: EUR {Terminal.sum_fees_D / Terminal.nr_quoted_ships_D if Terminal.nr_quoted_ships_D else 0:.1f}"
    )
    print("Diverted Feeder Ships:", Terminal.nr_diverted_ships_F)
    print("Diverted Deep-Sea Ships:", Terminal.nr_diverted_ships_D)
    print("Towed Feeder Ships:", Terminal.nr_towed_ships_F)
    print("Towed Deep-Sea Ships:", Terminal.nr_towed_ships_D)
    print("Docked Feeder Ships:", Terminal.nr_docked_ships_F)
    print("Docked Deep-Sea Ships:", Terminal.nr_docked_ships_D)
    print("Unloaded Feeder Ships:", Terminal.nr_unloaded_ships_F)
    print("Unloaded Deep-Sea Ships:", Terminal.nr_unloaded_ships_D)
    print(f"Ships Unloaded by Team Alpha: {Terminal.unloading_by_alpha}")
    print(f"Ships Unloaded by Team Bravo: {Terminal.unloading_by_bravo}")
    print(f"Ships Unloaded by Team Charlie: {Terminal.unloading_by_charlie}")
    print("Scanned Feeder Ships:", Terminal.nr_scanned_ships_F)
    print("Scanned Deep-Sea Ships:", Terminal.nr_scanned_ships_D)
    print("Feeder Loads Delivered Inland:", Terminal.nr_delivered_loads_F)
    print("Deep-Sea Loads Delivered Inland:", Terminal.nr_delivered_loads_D)
    print("Ships Needing Restacking:", Terminal.nr_restacked_ships)
    print(f"Restacking by Team Alpha: {Terminal.restacking_by_alpha}")
    print(f"Restacking by Team Bravo: {Terminal.restacking_by_bravo}")
    print(f"Restacking by Team Charlie: {Terminal.restacking_by_charlie}")
    print("Scans with a Minor Problem:", Terminal.nr_minor_problem)
    print("Scans with a Major Problem:", Terminal.nr_major_problem)

    print(
        "Feeder Ships Diverted:",
        compute_fraction_ships_diverted(Terminal, "feeder"),
    )
    print(
        "Deep-Sea Ships Diverted:",
        compute_fraction_ships_diverted(Terminal, "deepsea"),
    )
    print("Total Diversion:", compute_fraction_ships_diverted(Terminal, "all"))

    print("Restacking hours (alpha):", compute_team_restacking_time(Terminal, "alpha"))
    print("Restacking hours (bravo):", compute_team_restacking_time(Terminal, "bravo"))
    print(
        "Restacking hours (charlie):", compute_team_restacking_time(Terminal, "charlie")
    )
    print(f"Average Turnaround Time (feeder):  {avg_turnaround_F:.1f} h")
    print(f"Average Turnaround Time (deepsea): {avg_turnaround_D:.1f} h")
    print(f"Average Turnaround Time (all):     {avg_turnaround_all:.1f} h")
    print("\nArrival Rate Checks:")
    print(f"Average Total Ships per Week: {(total_ships / weeks):.1f} (Expected ~8)")
    if total_ships > 0:
        print(
            f"Percentage of Feeder Ships: {(Terminal.nr_arrived_ships_F / total_ships * 100):.1f}% (Expected ~65%)"
        )
        print(
            f"Percentage of Deep-Sea Ships: {(Terminal.nr_arrived_ships_D / total_ships * 100):.1f}% (Expected ~35%)"
        )
        print(
            f"Percentage of Feeder Ships That Needed Towing: {(Terminal.nr_towed_ships_F / Terminal.nr_docked_ships_F * 100):.1f}% (Expected ~30%)"
        )
        print(
            f"Percentage of Ships Unloaded by Team Alpha: {(Terminal.unloading_by_alpha / total_unloaded * 100):.1f}% (Expected ~40%)"
        )
        print(
            f"Percentage of Ships Unloaded by Team Bravo: {(Terminal.unloading_by_bravo / total_unloaded * 100):.1f}% (Expected ~35%)"
        )
        print(
            f"Percentage of Ships Unloaded by Team Charlie: {(Terminal.unloading_by_charlie / total_unloaded * 100):.1f}% (Expected ~25%)"
        )
        print(
            f"Percentage of Charlie Unloadings Needing Restacking: {(Terminal.nr_restacked_ships / Terminal.unloading_by_charlie * 100):.1f}% (Expected ~25%)"
        )
        print(
            f"Percentage of Loads Delivered: {(total_delivered / total_confirmed_ships * 100):.1f}% (Expected >= 95%)"
        )
        print(
            f"Percentage of Scans with a Minor Problem: {(Terminal.nr_minor_problem / total_scanned * 100):.1f}% (Expected ~8%)"
        )
        print(
            f"Percentage of Scans with a Major Problem: {(Terminal.nr_major_problem / total_scanned * 100):.1f}% (Expected ~2%)"
        )
    else:
        print("Percentage of Feeder Ships (F): 0.00% (No ships announced)")
        print("Percentage of Deep-Sea Ships (D): 0.00% (No ships announced)")
    plot_turnaround_times(
        Terminal.turnaround_points,
        start_hour=0.0,
        # end_hour=2000,
    )
    print("\nDONE\n")

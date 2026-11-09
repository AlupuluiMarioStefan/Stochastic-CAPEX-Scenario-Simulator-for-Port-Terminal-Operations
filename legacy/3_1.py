import json
with open('ship_arrival_information.json') as data:
    arrival_information = json.load(data)
import simpy
import random


WARMUP_HOURS = 1440.0
AGREED_TIME_FEEDER = 104.0
AGREED_TIME_DEEPSEA = 130.0
ONTIME_TARGET = 90.0


def compute_ontime_percentage(sim):
    # Pattern: Reporting - slides 14-15
    # On-time KPI computed from the counters of the measured ships.
    total = sim.total_F + sim.total_D 
    if total == 0:
        return 0
    else:
        return (sim.ontime_F + sim.ontime_D) * 100 / total 


def evaluate_investments(arrival_info, runs=10):
    # Pattern: Replications - slides 18-19
    # Every investment scenario is simulated `runs` times with a fresh simulator; the averages are compared (slide 19).
    team_options = [0, 1, 2]
    team_labels = {0: "No extra team", 1: "One extra team", 2: "Two extra teams"}
    team_costs = {0: 0, 1: 55000, 2: 77000}
    process_options = ["none", "automated", "second_customs"]
    process_labels = {"none": "No process investment", "automated": "Automated cranes", "second_customs": "Second customs team"}
    process_costs = {"none": 0, "automated": 35000, "second_customs": 28000}
    result = {}
    nr_warmup_ships = 0
    for team in team_options:
        for process in process_options:
            scores = []
            for run in range(runs):
                sim = ContainerTerminalSimulator()
                has_automated = (process == 'automated')
                has_customs = (process == 'second_customs')
                sim.simulate(arrival_info, extra_gangs = team, automated_cranes = has_automated, second_scanning_crew = has_customs)
                scores.append(compute_ontime_percentage(sim))
                nr_warmup_ships = sim.nr_warmup_ships
            average_score = sum(scores) / len(scores)
            result[(team, process)] = average_score
    print(f"\nShips left out as warm-up (announced before hour {WARMUP_HOURS:.0f}): {nr_warmup_ships}")
    print(f"\nOn-time handling percentage ({runs}-run average)\n")
    
    header = "Scenario         | "
    for process in process_options:
        header += f"{process_labels[process]:<24} | "
    print(header)
    print("-" * len(header))
    
    for team in team_options:
        row = f"{team_labels[team]:<16} | "
        for process in process_options:
            score = result[(team, process)]
            row += f"{score:.1f}%".ljust(24) + " | "
        print(row)
    cheapest_cost = float('inf')
    best_team = None
    best_process = None
    best_score = None
    for team in team_options:
        for process in process_options:
            score = result[(team, process)]
            if score >= ONTIME_TARGET:
                total_cost = team_costs[team] + process_costs[process]
                if total_cost < cheapest_cost:
                    cheapest_cost = total_cost
                    best_team = team
                    best_process = process
                    best_score = score
    if best_team is not None:
        print(f"\nCheapest alternative that meets {ONTIME_TARGET:.0f}%:")
        print(f"Combination: {team_labels[best_team]} + {process_labels[best_process]}")
        print(f"On time: {best_score:.1f}%")
        print(f"Cost: EUR {cheapest_cost:,}")
    else:
        print(f"\nNo alternative reaches the {ONTIME_TARGET:.0f}% requirement.")
    return result


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
        self.ontime_F = 0  # Count of feeder ships handled within the agreed handling time.
        self.ontime_D = 0  # Count of deep-sea ships handled within the agreed handling time.
        self.total_F = 0  # Count of feeder ships whose load reached the inland terminal.
        self.total_D = 0  # Count of deep-sea ships whose load reached the inland terminal.
        self.nr_warmup_ships = 0  # Count of ships announced during the warm-up period.

    # ---------------------------------- Simulation -----------------------------------
    # Pattern: Customer Generator (fixed arrival information) - slides 8, 10
    # Creates a ship at each announced time from the file instead of waiting a random inter-arrival time.
    def ship_generator(self, env, arrivals):
        for announce, ship_type in arrivals:
            yield env.timeout(max(0, announce - env.now))
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
        arrival_time = env.now
        confirmed_time = arrival_time + 120
        # Pattern: Warmup time - slide 18
        # Ships announced before the warm-up ends are simulated (they fill the queues) but not measured.
        measured = arrival_time >= WARMUP_HOURS
        if not measured:
            self.nr_warmup_ships += 1
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
        # Pattern: Choice (scenario switch) - slides 24-25
        # Automated cranes cut every unloading time by 3 h and let charlie restack by itself.
        if self.automated_cranes is True:
            cnt = 3
        else:
            cnt = 0
        draw = random.random()
        if draw < 0.4:
            team = self.team_alpha.request()
            yield team
            yield env.timeout(self.get_wait_until_open(env.now))
            yield env.timeout(8 - cnt)
            self.unloading_by_alpha += 1
            self.team_alpha.release(team)
        elif draw < 0.75:
            team = self.team_bravo.request()
            yield team
            yield env.timeout(self.get_wait_until_open(env.now))
            yield env.timeout(11 - cnt)
            self.unloading_by_bravo += 1
            self.team_bravo.release(team)
        else:
            team = self.team_charlie.request()
            yield team
            yield env.timeout(self.get_wait_until_open(env.now))
            yield env.timeout(16 - cnt)
            self.unloading_by_charlie += 1
            # Restacking - Pattern: Choice (nested) + Multiple resources - slides 24-25, 29
            # Charlie keeps its resource (20%) or releases it and requests team alpha or bravo.
            if random.random() < 0.25:
                if self.automated_cranes is True or random.random() < 0.2:
                    yield team
                    yield env.timeout(2)
                    self.restacking_by_charlie += 1
                    self.team_charlie.release(team)
                else:
                    self.team_charlie.release(team)
                    if random.random() < 0.5:
                        team = self.team_alpha.request()
                        yield team
                        yield env.timeout(2)
                        self.restacking_by_alpha += 1
                        self.team_alpha.release(team)
                    else:
                        team = self.team_bravo.request()
                        yield team
                        yield env.timeout(2)
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
        if measured:
            full_time = env.now - confirmed_time
            if ship_type == 'feeder':
                self.total_F += 1
                if full_time <= AGREED_TIME_FEEDER:
                    self.ontime_F += 1
            else:
                self.total_D += 1
                if full_time <= AGREED_TIME_DEEPSEA:
                    self.ontime_D += 1

    def simulate(self , arrival_info , * , extra_gangs: int = 0 , automated_cranes: bool = False , second_scanning_crew: bool = False,):
        env = simpy.Environment()
        self.automated_cranes = automated_cranes
        # Maps ship types from the dictionary to 'feeder' or 'deep-sea' and pairs them with arrival times in a list.
        arrivals = []
        times = arrival_info["ship_arrival_times"]
        type = arrival_info["ship_types"]
        for t, k in zip(times, type):
            if k == 'F':
                full_name = 'feeder'
            else:
                full_name = 'deep-sea'
            arrivals.append((t, full_name))
        # Simulation set-up - Pattern: Multiple resources - slides 11, 29
        # One Resource per crane team and for customs; the generator process is started and run.
        self.team_bravo = simpy.Resource(env, capacity = 2 if extra_gangs >= 1 else 1)
        self.team_charlie = simpy.Resource(env, capacity = 2 if extra_gangs >= 2 else 1)
        self.team_alpha = simpy.Resource(env, capacity = 1)
        self.customs = simpy.Resource(env, capacity = 2 if second_scanning_crew is True else 1)
        env.process(self.ship_generator(env , arrivals))
        env.run()
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

    with open("ship_arrival_information.json") as data:
        arrival_information = json.load(data)

    evaluate_investments(arrival_information, runs=10)

    Terminal = ContainerTerminalSimulator()
    simulation = Terminal.simulate(arrival_information)
    total_ships = Terminal.nr_arrived_ships_F + Terminal.nr_arrived_ships_D
    total_unloaded = Terminal.nr_unloaded_ships_F + Terminal.nr_unloaded_ships_D
    total_scanned = Terminal.nr_scanned_ships_F + Terminal.nr_scanned_ships_D
    total_confirmed_ships = (
        Terminal.nr_quoted_ships_F
        + Terminal.nr_quoted_ships_D
        - Terminal.nr_diverted_ships_F
        - Terminal.nr_diverted_ships_D
    )
    total_delivered = Terminal.nr_delivered_loads_F + Terminal.nr_delivered_loads_D
    weeks = 8760 / 168
    print("\nBase scenario without any investment")
    print("Simulation End Time:", round(simulation.now, 1))
    print("Total Feeder Ships Announced:", Terminal.nr_arrived_ships_F)
    print("Total Deep-Sea Ships Announced:", Terminal.nr_arrived_ships_D)
    print("Diverted Feeder Ships:", Terminal.nr_diverted_ships_F)
    print("Diverted Deep-Sea Ships:", Terminal.nr_diverted_ships_D)
    print("Unloaded Feeder Ships:", Terminal.nr_unloaded_ships_F)
    print("Unloaded Deep-Sea Ships:", Terminal.nr_unloaded_ships_D)
    print(f"Ships Unloaded by Team Alpha: {Terminal.unloading_by_alpha}")
    print(f"Ships Unloaded by Team Bravo: {Terminal.unloading_by_bravo}")
    print(f"Ships Unloaded by Team Charlie: {Terminal.unloading_by_charlie}")
    print("Feeder Loads Delivered Inland:", Terminal.nr_delivered_loads_F)
    print("Deep-Sea Loads Delivered Inland:", Terminal.nr_delivered_loads_D)
    print(
        f"On-Time Feeder Ships: {Terminal.ontime_F} of {Terminal.total_F}"
        f" (agreed handling time {AGREED_TIME_FEEDER:.0f} h)"
    )
    print(
        f"On-Time Deep-Sea Ships: {Terminal.ontime_D} of {Terminal.total_D}"
        f" (agreed handling time {AGREED_TIME_DEEPSEA:.0f} h)"
    )
    print("Ships Left Out as Warm-Up:", Terminal.nr_warmup_ships)
    print(f"On-Time Percentage: {compute_ontime_percentage(Terminal):.1f}%")
    print("\nArrival Rate Checks:")
    print(f"Average Total Ships per Week: {(total_ships / weeks):.1f}")
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
            f"Percentage of Loads Delivered: {(total_delivered / total_confirmed_ships * 100):.1f}% (Expected 100%)"
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

    print("\nDONE\n")

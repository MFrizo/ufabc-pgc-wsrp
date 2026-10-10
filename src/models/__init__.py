"""
Package: models
Description: Registry of the WSRP model versions, shared by main.py and the notebook.
"""

from src.models.model_0 import build_model_m0
from src.models.model_1 import build_model_m1
from src.models.model_2 import build_model_m2
from src.models.model_3 import build_model_m3
from src.models.model_4 import build_model_m4
from src.models.model_5 import build_model_m5
from src.models.model_6 import build_model_m6
from src.models.model_7 import build_model_m7, LUNCH_DURATION, LUNCH_WINDOW, MAX_DAY_LENGTH
from src.models.model_8 import build_model_m8
from src.models.model_9 import build_model_m9

BUILDERS = {
    'm0': build_model_m0,  # Case 1: TSP
    'm1': build_model_m1,  # Case 2: TSPTW
    'm2': build_model_m2,  # Case 3: VRPTW
    'm3': build_model_m3,  # Case 4: SDVRPTW
    'm4': build_model_m4,  # Case 5: VRPTWWVST
    'm5': build_model_m5,  # Case 6: TDVRPTW
    'm6': build_model_m6,  # Case 7: FSMVRPTW
    'm7': build_model_m7,  # Case 8.a: MO-DOMDVRPTW-SD
    'm8': build_model_m8,  # Case 8.b: HC-DOMDVRPTW-SD
    'm9': build_model_m9,  # Case 8.a with flexible visits: MO-DOMDVRPTW-SD, a share of the visits booked
}

# Models that route a single broker, so they ignore a number of brokers
SINGLE_BROKER_MODELS = ('m0', 'm1')

# Models that book every visit at its earliest start h_i, so every visit has a strict time
STRICT_TIME_MODELS = ('m7', 'm8')

# Rush hours from 08:00 to 10:00 and from 17:00 at half the speed of the rest of the day
RUSH_HOURS = [(0, 1.0), (120, 2.0), (540, 1.0)]

# The speed outside rush hours all day long, for the models with a single travel time t_ij
NORMAL_SPEED = [(0, 2.0)]

# Generator settings each model runs with, on top of generate_wsrp_instance's defaults
INSTANCE_SETTINGS = {
    'm0': {},
    'm1': {},
    'm2': {'num_brokers': 2, 'fixed_ratio': 1.0},  # Case 3: every visit has a fixed time
    'm3': {'num_brokers': 2, 'fixed_ratio': 1.0},  # Case 4: same, some visits with a broker
    'm4': {'num_brokers': 2, 'fixed_ratio': 1.0, 'service_time_variation': 30},  # Case 5: 30 to 90 min visits
    'm5': {'num_brokers': 2, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': RUSH_HOURS},  # Case 6: travel time by period of the day
    'm6': {'num_brokers': 3, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': RUSH_HOURS},  # Case 7: more brokers than needed, to minimize the fleet
    'm7': {'num_brokers': 3, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': NORMAL_SPEED, 'start_at_homes': True,
           'lunch_break': (*LUNCH_WINDOW, LUNCH_DURATION),
           'max_day_length': MAX_DAY_LENGTH},  # Case 8.a: own homes, lunch, 08:00 to 17:00 days of up to 12 hours
    'm8': {'num_brokers': 3, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': NORMAL_SPEED, 'days_off': 1, 'split_shifts': True},  # Case 8.b: own shifts, one broker off
}
# M9 is M7's instance with half the visits booked; with fixed_ratio 1.0 it is M7's instance
INSTANCE_SETTINGS['m9'] = {**INSTANCE_SETTINGS['m7'], 'fixed_ratio': 0.5}

# Seed of each model's default run
DEFAULT_SEED = 42
DEFAULT_SEEDS = {
    'm7': 8,  # 2 brokers serve 5 to 7 properties; from 8 on, the third one is needed
    'm9': 8,  # M7's default instance, apart from the flexible visits
}

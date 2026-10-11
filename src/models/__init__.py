"""
Package: models
Description: Registry of the WSRP model versions, shared by main.py and the notebook.
"""

from src.models.model_0_0 import build_model_m0_0
from src.models.model_0_1 import build_model_m0_1
from src.models.model_0_2 import build_model_m0_2
from src.models.model_0_3 import build_model_m0_3
from src.models.model_0_4 import build_model_m0_4
from src.models.model_0_5 import build_model_m0_5
from src.models.model_0_6 import build_model_m0_6
from src.models.model_1 import build_model_m1, LUNCH_DURATION, LUNCH_WINDOW, MAX_DAY_LENGTH
from src.models.model_1_a import build_model_m1_a
from src.models.model_2 import build_model_m2
from src.models.model_3 import build_model_m3

# m0.0 to m0.6 are the sub-steps that build up to m1, the first complete model.
# m1.a is the subcase of m1 with a share of the visits booked. m2 is broker-focused.
# m3 is the Pareto front between the agency's objective and the brokers'.
BUILDERS = {
    'm0.0': build_model_m0_0,  # Sub-step: TSP
    'm0.1': build_model_m0_1,  # Sub-step: TSPTW
    'm0.2': build_model_m0_2,  # Sub-step: VRPTW
    'm0.3': build_model_m0_3,  # Sub-step: SDVRPTW
    'm0.4': build_model_m0_4,  # Sub-step: VRPTWWVST
    'm0.5': build_model_m0_5,  # Sub-step: TDVRPTW
    'm0.6': build_model_m0_6,  # Sub-step: FSMVRPTW
    'm1': build_model_m1,  # First complete model: MO-DOMDVRPTW-SD
    'm1.a': build_model_m1_a,  # Subcase of m1: a share of the visits booked
    'm2': build_model_m2,  # Broker-focused model: HC-DOMDVRPTW-SD
    'm3': build_model_m3,  # Pareto front of the agency and the brokers
}

# Models that route a single broker, so they ignore a number of brokers
SINGLE_BROKER_MODELS = ('m0.0', 'm0.1')

# Models that book every visit at its earliest start h_i, so every visit has a strict time
STRICT_TIME_MODELS = ('m1', 'm2', 'm3')

# Rush hours from 08:00 to 10:00 and from 17:00 at half the speed of the rest of the day.
# Synthetic trips and drawn points use these speeds. A cached real street duration is
# scaled by the congestion factors in src.core.travel instead.
RUSH_HOURS = [(0, 1.0), (120, 2.0), (540, 1.0)]

# The speed outside rush hours all day long, for the models with a single travel time t_ij
NORMAL_SPEED = [(0, 2.0)]

# Generator settings each model runs with, on top of generate_wsrp_instance's defaults.
# M1.a is M1's instance with half the visits booked; with fixed_ratio 1.0 it is M1's instance.
_M1_SETTINGS = {'num_brokers': 3, 'fixed_ratio': 1.0, 'service_time_variation': 30,
                'speed_profile': NORMAL_SPEED, 'start_at_homes': True,
                'lunch_break': (*LUNCH_WINDOW, LUNCH_DURATION),
                'max_day_length': MAX_DAY_LENGTH}  # own homes, lunch, 08:00 to 17:00 days of up to 12 hours
INSTANCE_SETTINGS = {
    'm0.0': {},
    'm0.1': {},
    'm0.2': {'num_brokers': 2, 'fixed_ratio': 1.0},  # every visit has a fixed time
    'm0.3': {'num_brokers': 2, 'fixed_ratio': 1.0},  # same, some visits with a broker
    'm0.4': {'num_brokers': 2, 'fixed_ratio': 1.0, 'service_time_variation': 30},  # 30 to 90 min visits
    'm0.5': {'num_brokers': 2, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': RUSH_HOURS},  # travel time by period of the day
    'm0.6': {'num_brokers': 3, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': RUSH_HOURS},  # more brokers than needed, to minimize the fleet
    'm1': _M1_SETTINGS,
    'm1.a': {**_M1_SETTINGS, 'fixed_ratio': 0.5},
    'm2': {'num_brokers': 3, 'fixed_ratio': 1.0, 'service_time_variation': 30,
           'speed_profile': NORMAL_SPEED, 'days_off': 1, 'split_shifts': True},  # own shifts, one broker off
    'm3': {**_M1_SETTINGS, 'days_off': 1},  # M1's day, plus one broker off, for the front
}

# Seed of each model's default run
DEFAULT_SEED = 42
DEFAULT_SEEDS = {
    'm1': 8,  # 2 brokers serve 5 to 7 properties; from 8 on, the third one is needed
    'm1.a': 8,  # M1's default instance, apart from the flexible visits
}

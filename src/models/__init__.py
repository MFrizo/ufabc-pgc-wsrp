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

BUILDERS = {
    'm0': build_model_m0,  # Case 1: TSP
    'm1': build_model_m1,  # Case 2: TSPTW
    'm2': build_model_m2,  # Case 3: VRPTW
    'm3': build_model_m3,  # Case 4: SDVRPTW
    'm4': build_model_m4,  # Case 5: VRPTWWVST
    'm5': build_model_m5,  # Case 6: TDVRPTW
    'm6': build_model_m6,  # Case 7: FSMVRPTW
}

# Rush hours from 08:00 to 10:00 and from 17:00 at half the speed of the rest of the day
RUSH_HOURS = [(0, 1.0), (120, 2.0), (540, 1.0)]

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
}

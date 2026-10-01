"""
Package: models
Description: Registry of the WSRP model versions, shared by main.py and the notebook.
"""

from src.models.model_0 import build_model_m0
from src.models.model_1 import build_model_m1
from src.models.model_2 import build_model_m2
from src.models.model_3 import build_model_m3
from src.models.model_4 import build_model_m4

BUILDERS = {
    'm0': build_model_m0,  # Case 1: TSP
    'm1': build_model_m1,  # Case 2: TSPTW
    'm2': build_model_m2,  # Case 3: VRPTW
    'm3': build_model_m3,  # Case 4: SDVRPTW
    'm4': build_model_m4,  # Case 5: VRPTWWVST
}

# Generator settings each model runs with, on top of generate_wsrp_instance's defaults
INSTANCE_SETTINGS = {
    'm0': {},
    'm1': {},
    'm2': {'num_brokers': 2, 'fixed_ratio': 1.0},  # Case 3: every visit has a fixed time
    'm3': {'num_brokers': 2, 'fixed_ratio': 1.0},  # Case 4: same, some visits with a broker
    'm4': {'num_brokers': 2, 'fixed_ratio': 1.0, 'service_time_variation': 30},  # Case 5: 30 to 90 min visits
}

from typing import Dict, Any


def generate_wsrp_instance() -> Dict[str, Any]:
    """
    Generates a syntect instance of the Workforce Scheduling and Routing Problem (WSRP).
    Returns dictionaries of the sets and parameters to be injected at Pyomo model.
    """
    # Set K: Available Brokers (Ex: k1, k2)
    brokers = ['k1', 'k2']

    # Set C: Real Properties/Visits (Ex: v1, v2, v3)
    visits = ['v1', 'v2', 'v3']

    # Set V: Vertices (Visits + Depot 'd')
    vertices = ['d'] + visits

    # Parameter t_ij: Travel Time Matrix (simple mock)
    travel_times = {
        ('d', 'd'): 0,
        ('d', 'v1'): 10,
        ('d', 'v2'): 15,
        ('d', 'v3'): 20,
        ('v1', 'v1'): 0,
        ('v1', 'd'): 10,
        ('v1', 'v2'): 5,
        ('v1', 'v3'): 12,
        ('v2', 'v2'): 0,
        ('v2', 'd'): 15,
        ('v2', 'v1'): 5,
        ('v2', 'v3'): 8,
        ('v3', 'v3'): 0,
        ('v3', 'd'): 20,
        ('v3', 'v1'): 12,
        ('v3', 'v2'): 8
    }

    # Returns the final payload
    return {
        'K': brokers,
        'C': visits,
        'V': vertices,
        'distances': travel_times,
        'big_M': 1000  # Constant for linear relaxation (Big-M)
    }

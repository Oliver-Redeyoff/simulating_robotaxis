from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum

Coord = Tuple[float, float]

@dataclass
class lane:
    id: str
    speed: float
    shape: List[Coord]
    allow: List[str]
    disallow: List[str]

@dataclass
class edge:
    id: str
    is_drivable: bool
    lanes: List[lane]

@dataclass
class count():
    hour: int
    value_sum: int
    value_count: int

@dataclass
class count_point():
    id: str
    road_name: str
    latitude: float
    longitude: float
    utm: any
    counts: List[count]
    closest_lane: Tuple[float, lane]

@dataclass
class taz:
    id: str
    name: str
    edges: List[str]
    drivable_edges: List[str]
    node_count: int
    weight: float
    area: float

@dataclass
class simulation:
    start_hour: int
    start_time: float
    end_hour: int
    end_time: float
    net_file: str
    base_routes_file: str
    taxi_routes_file: str

@dataclass
class trip:
    id: int
    depart: float
    from_: str
    to: str
    def __lt__(self, other):
         return self.depart < other.depart

@dataclass
class commuter:
    home_edge: edge
    destination_edge: edge
    trip1: trip
    trip2: trip

class p(Enum):
    count_point_id = 0
    direction_of_travel = 1
    year = 2
    count_date = 3
    hour = 4
    region_id = 5
    region_name = 6
    local_authority_id = 7
    local_authority_name = 8
    road_name = 9
    road_type = 10
    start_junction_road_name = 11
    end_junction_road_name = 12
    easting = 13
    northing = 14
    latitude = 15
    longitude = 16
    link_length_km = 17
    link_length_miles = 18
    pedal_cycles = 19
    two_wheeled_motor_vehicles = 20
    cars_and_taxis = 21
    buses_and_coaches = 22
    lgvs = 23
    hgvs_2_rigid_axle = 24
    hgvs_3_rigid_axle = 25
    hgvs_4_or_more_rigid_axle = 26
    hgvs_3_or_4_articulated_axle = 27
    hgvs_5_articulated_axle = 28
    hgvs_6_articulated_axle = 29
    all_hgvs = 30
    all_motor_vehicles = 31

class taxi_states(Enum):
    any_state = -1      # all taxis
    empty = 0           # taxi is waiting
    pickup = 1          # taxi is en-route to pick a customer up
    occupied = 2        # taxi has a customer
    pickup_occupied = 3 # taxi has a customer but will pickup more customers

class reservation_states(Enum):
    any_state = 0
    new = 1
    old = 2
    assigned = 4
    picked_up = 8

    
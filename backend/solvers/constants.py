# Standard Physical and Engineering Constants
# SI Units

# Gravitational acceleration (m/s²)
G = 9.81
G_EARTH = 9.81

# Mathematical constants
PI = 3.141592653589793
E = 2.718281828459045

# Fluid properties (water at 20°C, 1 atm)
WATER_DENSITY = 1000  # kg/m³
WATER_VISCOSITY = 0.001  # Pa·s (dynamic viscosity)
WATER_KINEMATIC_VISCOSITY = 1e-6  # m²/s

# Air properties (at 20°C, 1 atm)
AIR_DENSITY = 1.204  # kg/m³
AIR_VISCOSITY = 1.81e-5  # Pa·s

# Material properties
STEEL_DENSITY = 7850  # kg/m³
ALUMINUM_DENSITY = 2700  # kg/m³
CONCRETE_DENSITY = 2400  # kg/m³

# Modulus of elasticity (Young's modulus) in Pa
STEEL_YOUNGS_MODULUS = 200e9  # Pa (200 GPa)
ALUMINUM_YOUNGS_MODULUS = 70e9  # Pa (70 GPa)

# Standard gravity (SI)
STD_GRAVITY = 9.80665  # m/s²

# Standard atmospheric pressure
ATM_PRESSURE = 101325  # Pa

# Speed of light
SPEED_OF_LIGHT = 299792458  # m/s

# Boltzmann constant
BOLTZMANN = 1.380649e-23  # J/K

# Planck constant
PLANCK = 6.62607015e-34  # J·s

def get_constant(name: str):
    """Retrieve a constant by name (case-insensitive)"""
    constants = {
        'g': G,
        'gravity': G,
        'pi': PI,
        'e': E,
        'water_density': WATER_DENSITY,
        'water_viscosity': WATER_VISCOSITY,
        'air_density': AIR_DENSITY,
        'air_viscosity': AIR_VISCOSITY,
        'steel_density': STEEL_DENSITY,
        'aluminum_density': ALUMINUM_DENSITY,
        'concrete_density': CONCRETE_DENSITY,
        'youngs_modulus': STEEL_YOUNGS_MODULUS,
        'atm_pressure': ATM_PRESSURE,
        'c': SPEED_OF_LIGHT,
        'speed_of_light': SPEED_OF_LIGHT,
    }
    return constants.get(name.lower())

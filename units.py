from pint import UnitRegistry, Quantity

UNIT_REGISTRY = UnitRegistry()
Q_: type[Quantity] = UNIT_REGISTRY.Quantity

"""Combine documented suggestions with the shared saved teaching-space records."""
from .catalog import BUILDING_NAMES, ROOM_CATALOGUE, ROOM_TYPES, building_identity_key, room_identity_key
from .models import Building, Room


def building_names():
    choices = {building_identity_key(name): name for name in BUILDING_NAMES}
    for name in Building.objects.values_list('name', flat=True):
        choices[building_identity_key(name)] = name
    return tuple(choices.values())


def room_catalogue():
    choices = {room_identity_key(item['name']): {**item, 'identity': room_identity_key(item['name']),
                                               'aliases': list(item['aliases'])} for item in ROOM_CATALOGUE}
    for name in Room.objects.order_by('name').values_list('name', flat=True):
        key = room_identity_key(name)
        previous = choices.get(key, {'name': name, 'aliases': []})
        aliases = [*previous['aliases'], *([previous['name']] if previous['name'] != name else [])]
        choices[key] = {**previous, 'name': name, 'identity': key, 'aliases': list(dict.fromkeys(aliases))}
    return tuple(choices.values())


def room_types():
    choices = {value.casefold(): value for value in ROOM_TYPES}
    for value in Room.objects.order_by('room_type').values_list('room_type', flat=True).distinct():
        if value:
            choices.setdefault(value.strip().casefold(), value)
    return tuple(choices.values())

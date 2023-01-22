import yaml
import json
import argparse

def main():
    input_json_file = 'MMMM_mystery.json'
    ouput_yaml_file = 'MMMM_mystery.yaml'
    with open(input_json_file, "r", encoding='utf-8') as f:
        input_json = json.load(f)

    mystery = {
        'description': 'Mystery'
    }
    
    IGNORE = [
        'enemizercli',
        'saveonexit',
        'calc_playthrough',
        'create_spoiler',
        'mystery',
        'bps',
        'collection_rate',
    ]

    SETTING_MAP = {
        'goal': 'goals',
        'bigkeyshuffle': 'bigkey_shuffle',
        'keyshuffle': 'smallkey_shuffle',
        'compassshuffle': 'compass_shuffle',
        'mapshuffle': 'map_shuffle',
        'swords': 'weapons',
        'crystals_ganon': 'ganon_open',
        'crystals_gt': 'tower_open',
        'mode': 'world_state',
        'shuffle': 'entrance_shuffle',
        "shuffleenemies": 'enemy_shuffle',
        "shufflebosses": 'boss_shuffle',
        'logic': 'glitches_required',
        'difficulty': 'item_pool'
    }
    OPTION_MAP = {
        'goals': {
            'crystals': 'fast_ganon',
            'triforcehunt': 'triforce-hunt'
        },
        'weapons': {
            'random': 'randomized'
        },
        'glitches_required': {
            'noglitches': 'none',
            'owglitches': 'owg',
            'no_logic': 'nologic'
        }
    }

    for setting,option in input_json.items():
        if setting in IGNORE:
            continue
        if setting == 'startinventory':
            items = option.split(',')
            mystery[setting] = {}
            for item in items:
                mystery[setting][item] = 'on'
        else:
            setting = SETTING_MAP[setting] if setting in SETTING_MAP else setting
            if option in (0,1) and setting not in ('ganon_open', 'tower_open', 'beemizer'):
                option = 'on' if option == 1 else 'off'
            option = OPTION_MAP[setting][option] if setting in OPTION_MAP and option in OPTION_MAP[setting] else option
            mystery[setting] = option

    with open(ouput_yaml_file, "w+", encoding='utf-8') as f:
        yaml.dump(mystery,f, Dumper=yaml.SafeDumper, encoding='utf-8', allow_unicode=True, default_flow_style=False)

if __name__ == '__main__':
    main()
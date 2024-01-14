import json
import argparse
import random
import copy
import sys
import numpy as np

MAX_ATTEMPTS = 2000

# Non-potchecks
NONDUNGEON = 93
DUNGEON = 8 + 6 + 6 + 6 + 2 + 14 + 10 + 8 + 8 + 8 + 8 + 12 + 27
KEYDROPS = 13
SHOPSANITY = 32
TAKE_ANY = 9

# Pottery
keys = 19
cave = 144
dungeon = 38 + 52 + 50 + 37 + 27 + 39 + 61 + 83 + 46 + 55 + 40 + 51 + 93 - 13

POTTERY = {
    'none': 0,
    'keys': keys,
    'cave': cave,
    'dungeon': dungeon,
    'cavekeys': cave + keys,
    'lottery': dungeon + cave,
    'reduced': cave + int(dungeon*0.25),
    'reduced_dungeon': int(dungeon*0.25),
    'clustered': cave + int(dungeon*0.25),
    'clustered_dungeon': int(dungeon*0.5),
    'nonempty': int((dungeon + cave)*0.9),
    'nonempty_dungeon': int((dungeon)*0.9)
}

# Progression counts
INVENTORY = 41
MAPSANDCOMPASSES = 24
BIGKEYS = 11
SMALLKEYS = 29
BOSSHEARTS = 11
SHOPUPGRADES = 2 + 3
RETRO_ARROWS = 3

def print_to_stdout(*a) -> None:
    print(*a, file=sys.stdout)

def make_mystery(input_weights, default_settings, args):
    def within_limits(score: dict) -> bool:
        """Check if the score is within the limits of the input weights"""
        for attr,min,max in attrs:
            score_val = score[attr]
            if score_val < min or score_val > max:
                return False
        return True
   
    def roll_setting(setting_name: str) -> None:
        """Randomly select a setting based on its weights and update the score accordingly."""
        options = list(input_weights[setting_name].keys())
        weights = [input_weights[setting_name][option]['weight'] for option in options]

        if not weights:
            return

        choice = random.choices(options, weights=weights, k=1)[0]

        for attr,_,_ in attrs:
            score[attr] += input_weights[setting_name][choice][attr]

        # Some arbitrary settings need to be bools instead of ints
        if setting_name not in ['progressive', 'dungeon_counters', 'openpyramid', 'dropshuffle']:
            if choice == 'on':
                choice = 1
            if choice == 'off':
                choice = 0

        settings[setting_name] = choice

    def force_setting(setting_name: str, choice) -> None:
        """Force a setting to a specific value"""
        for key in input_weights[setting_name]:
            if key == choice:
                input_weights[setting_name][key]['weight'] = 1
            else:
                input_weights[setting_name][key]['weight'] = 0

    def determine_pool_size() -> int:
        """Determine the size of the item pool based on the settings"""
        pool_size = NONDUNGEON
        pool_size += DUNGEON
        pool_size += POTTERY[settings['pottery']]
        if settings['dropshuffle'] != 'none':
            pool_size += KEYDROPS
        if settings['shopsanity'] == 1:
            pool_size += SHOPSANITY
        if settings['take_any'] != 'none':
            pool_size += TAKE_ANY
        return pool_size
    
    def determine_mandatory_pool_size() -> int:
        """Determine the size of the mandatory item pool based on the settings"""
        mandatory_pool_size = INVENTORY + MAPSANDCOMPASSES + BIGKEYS + SMALLKEYS + BOSSHEARTS
        if settings['shopsanity'] == 1:
            mandatory_pool_size += SHOPUPGRADES
        if settings['dropshuffle'] != 'none':
            mandatory_pool_size += KEYDROPS
        if settings['take_any'] != 'none':
            mandatory_pool_size += TAKE_ANY
        if settings['bow_mode'] in ['retro', 'retro_silvers']:
            mandatory_pool_size += RETRO_ARROWS
        if settings['pottery'] not in ['none', 'cave']:
            mandatory_pool_size += POTTERY['keys']
        return mandatory_pool_size        

    def simulate_tfh(goal:int, pool:int, total:int) -> tuple:
        """Simulate a triforce hunt run to estimate the average time to completion"""
        if total < 300:
            cpm = 1.7
            if settings['shuffle'] != 'vanilla':
                cpm = cpm*0.8
        elif total < 500:
            cpm = 3.3
        elif total < 1000:
            cpm = 4
        else:
            cpm = 5.3

        if settings['door_shuffle'] != 'vanilla':
            cpm = cpm*0.9

        time_per_run = [None]*500

        for i in range(500):
            bag = ['pool']*pool + ['junk']*(total-pool)
            np.random.shuffle(bag)
            accumulator = 0
            for checks,item in enumerate(bag):
                if item == 'pool':
                    accumulator += 1
                    if accumulator == goal:
                        break
            time_per_run[i] = checks/cpm 
        
        mean_time = np.mean(time_per_run)
        std_dev = np.std(time_per_run)
        length = int((mean_time-100)/10)-2
        variance = int((std_dev-3)*2)+1

        return length, variance

    def triforcehunt() -> list:
        roll_weights = []
        minimum_pool_size = determine_mandatory_pool_size()
        current_pool_size = determine_pool_size()
        pool_space = current_pool_size - minimum_pool_size
        base_fraction = current_pool_size / 216
        
        tfh_goal_weights = input_weights.get('tfh_goal', {})
        tfh_extra_pool_weights = input_weights.get('tfh_extra_pool', {})

        rolls = [int(tf_goalfraction) for tf_goalfraction, goalpoints in tfh_goal_weights.items() if random.random() < goalpoints['weight']]
        for tf_goalfraction in rolls:
            tf_goal = int(tf_goalfraction * base_fraction * random.uniform(0.85, 1.15))
            for tf_pooldelta, poolpoints in tfh_extra_pool_weights.items():
                tf_pool = int(tf_goal * (1 + int(tf_pooldelta) / 100) + 1)
                if tf_pool <= tf_goal:
                    continue
                if pool_space - tf_pool < 50 or tf_pool / pool_space > 0.8:
                    continue
                if random.random() > poolpoints['weight']:
                    continue
                length, variance = simulate_tfh(tf_goal, tf_pool, current_pool_size)
                familiarity = poolpoints['familiarity']
                execution = poolpoints['execution']
                roll_weights.append([tf_goal, tf_pool, length, execution, familiarity, variance])
        return roll_weights

    def better_than_current(new_points:dict) -> bool:
        """Determine if the new points are closer to the target than the current score"""
        delta_score = 0

        for attr, attr_min, attr_max in attrs:
            current_score = score[attr] 
            new_score = new_points[attr]

            if current_score < attr_min:
                delta_score += new_score

            elif current_score > attr_max:
                delta_score -= new_score

            elif new_score + current_score < attr_min or current_score + new_score > attr_max:
                return False

        return delta_score > 0

    def item_within_limits(new_points:dict) -> bool:
        """Determine if the new points are within the limits of the input weights"""
        for attr, attr_min, attr_max in attrs:
            new_score = score[attr] + new_points[attr]
            if new_score < attr_min or new_score > attr_max:
                return False
        return True 
    
    def set_input_weight(setting_name:str, option:str, weight:int) -> None:
        input_weights[setting_name][option]['weight'] = weight

    attrs = [
        ('length', args.min_length, args.max_length),
        ('execution', args.min_execution, args.max_execution),
        ('familiarity', args.min_familiarity, args.max_familiarity),
        ('variance', args.min_variance, args.max_variance)
    ]
    cached_weights = copy.deepcopy(input_weights)
    attempts = 0
    while attempts <= MAX_ATTEMPTS:
        if attempts == 300:
            cached_weights['goal']['triforcehunt']['weight'] = 0
            cached_weights['goal']['ganonhunt']['weight'] = 0
        attempts += 1
        settings = copy.copy(default_settings)
        input_weights = copy.deepcopy(cached_weights)
        set_input_weight('algorithm', 'vanilla_fill', 0)
        startinventory = []
        score = {}
        for attr,_,_ in attrs:
            score[attr] = 0

        roll_setting('logic')
        if settings['logic'] != 'noglitches':
            force_setting('pseudoboots', 'off')
            startinventory.append('Pegasus Boots')
            set_input_weight('startinventory', 'Pegasus Boots', 0)
        if settings['logic'] == 'hybridglitches':
            force_setting('door_shuffle', 'vanilla') 

        roll_setting('goal')
        if settings['goal'] in ['triforcehunt', 'ganonhunt', 'trinity']:
            set_input_weight('algorithm', 'major_only', 0)
        if settings['goal'] == 'ganonhunt':
            force_setting('openpyramid', 'on')
            force_setting('shuffle', 'vanilla')
        if settings['goal'] == 'completionist':
            force_setting('accessibility', 'locations')
            force_setting('mystery', 'off')
            force_setting('timer', 'none')
            force_setting('shopsanity', 'off')
        if settings['goal'] in ('ganon', 'crystals'):
            roll_setting('crystals_ganon')
        if settings['goal'] == 'crystals':
            force_setting('openpyramid', 'on')

        roll_setting('mode')
        if settings['mode'] == 'standard':
            set_input_weight('boots_hint', 'on', 1)
            set_input_weight('boots_hint', 'off', 1)
            set_input_weight('shuffle', 'insanity', 0)
            force_setting('flute_mode', 'normal')
             
        roll_setting('timer')
        if settings['timer'] != 'none':
            force_setting('shuffleenemies', 'none')
            force_setting('shufflebosses', 'none')
            set_input_weight('pottery', 'dungeon', 0)
            set_input_weight('pottery', 'reduced', 0)
            set_input_weight('pottery', 'lottery', 0)

        roll_setting('shuffleenemies')
        if settings['shuffleenemies'] != 'none' and settings['mode'] == 'standard':
            force_setting('swords', 'assured')
        if settings['shuffleenemies'] != 'none':
            set_input_weight('swords', 'swordless', 0)
            set_input_weight('enemy_health', 'hard', 0)
            set_input_weight('enemy_health', 'expert', 0)

        roll_setting('shuffle')
        if settings['shuffle'] == 'vanilla':
            force_setting('shuffleganon', 'off')
            force_setting('shufflelinks', 'off')
            force_setting('shuffletavern', 'off')
            force_setting('overworld_map', 'default')
            force_setting('take_any', 'none')
        if settings['shuffle'] == 'lean':
            set_input_weight('pottery', 'lottery', 0)
            set_input_weight('pottery', 'reduced', 0)
            set_input_weight('pottery', 'cave', 0)
            set_input_weight('pottery', 'cavekeys', 0)
            force_setting('shopsanity', 'off')
        if settings['shuffle'] == 'insanity':
            force_setting('bombbag', 'off')
            startinventory.append('Ocarina')
            set_input_weight('startinventory', 'Ocarina', 0)

        if settings['shuffle'] != 'vanilla':
            if settings['goal'] == 'ganonhunt':
                force_setting('shuffleganon', 'off')
                force_setting('openpyramid', 'on')
            else:
                force_setting('shuffleganon', 'on')
                force_setting('openpyramid', 'off')
            if settings['mode'] == 'inverted':
                force_setting('shufflelinks', 'on')
            set_input_weight('take_any', 'random', 0)
            set_input_weight('take_any', 'fixed', 0)

        if settings['shuffle'] == 'vanilla' and settings['goal'] == 'ganon':
            max_gt = int(settings['crystals_ganon'])
            for key in input_weights['crystals_gt']:
                if int(key) > max_gt:
                    set_input_weight('crystals_gt', key, 0)
                else:
                    input_weights['crystals_gt'][key]['length'] = 0
                    input_weights['crystals_gt'][key]['execution'] = 0
            roll_setting('crystals_gt')
        elif settings['shuffle'] == 'vanilla' and settings['goal'] == 'ganonhunt' and settings['openpyramid'] == 0:
            settings['crystals_gt'] = "0"
        elif settings['shuffle'] == 'vanilla' and settings['goal'] == 'crystals':
            settings['crystals_gt'] = str(random.randint(int(settings['crystals_ganon']),7))
        else:
            settings['crystals_gt'] = str(random.randint(0,7))

        roll_setting('door_shuffle')
        if settings['door_shuffle'] != 'vanilla':
            force_setting('dungeon_counters', 'on')
            force_setting('trap_door_mode', 'boss')
            force_setting('accessibility', 'locations')
            roll_setting('intensity')
            roll_setting('door_type_mode')
            roll_setting('decoupledoors')
            roll_setting('trap_door_mode')

        roll_setting('pottery')
        if settings['pottery'] not in ('none', 'cave'):
            force_setting('dungeon_counters', 'on')
            force_setting('dropshuffle', 'keys')
        if settings['pottery'] not in ('none', 'cave', 'keys', 'cavekeys') and settings['goal'] not in ['triforcehunt', 'ganonhunt']:
            force_setting('wild_dungeon_items', 'mcsb')
        if settings['pottery'] != 'none':
            settings['colorizepots'] = 1

        roll_setting('wild_dungeon_items')
        if 'm' in settings['wild_dungeon_items'] and 'c' in settings['wild_dungeon_items'] and 's' in settings['wild_dungeon_items'] and 'b' in settings['wild_dungeon_items']:
            force_setting('restrict_boss_items', 'none')
        elif 'm' in settings['wild_dungeon_items'] and 'c' in settings['wild_dungeon_items']:
            set_input_weight('restrict_boss_items', 'mapcompass', 0)
        
        if 'm' in settings['wild_dungeon_items']:
            settings['mapshuffle'] = 1
        if 'c' in settings['wild_dungeon_items']:
            settings['compassshuffle'] = 1
        if 's' in settings['wild_dungeon_items']:
            roll_setting('universal_small_keys')
            settings['keyshuffle'] = 'wild' if settings['universal_small_keys'] == 0 else 'universal'
            del settings['universal_small_keys']
        if 'b' in settings['wild_dungeon_items']:
            settings['bigkeyshuffle'] = 1
        del settings['wild_dungeon_items']

        if settings['keyshuffle'] != 'universal':
            set_input_weight('startinventory', 'Small Key (Universal),Small Key (Universal),Small Key (Universal)', 0)

        roll_setting('bow_mode')
        if settings['bow_mode'] in  ['retro', 'retro_silvers']:
            input_weights['startinventory']['Bow'] = input_weights['startinventory'].pop('Progressive Bow')
            set_input_weight('startinventory', 'Arrow Upgrade (+10)', 0)

        roll_setting('difficulty')
        if settings['difficulty'] in ['hard','expert']:
            set_input_weight('startinventory', 'Progressive Armor,Progressive Armor', 0)

        roll_setting('bombbag')
        if settings['bombbag'] == 1:
            set_input_weight('startinventory', 'Bomb Upgrade (+10)', 0)
            set_input_weight('startinventory', 'Bombs (10)', 0)

        roll_setting('shopsanity')

        roll_setting('mystery')
        if settings['shopsanity'] == 0 and settings['pottery'] == 'none' and settings['goal'] != 'completionist':
            force_setting('collection_rate', 'off')
        roll_setting('collection_rate')

        if settings['pottery'] not in ['none', 'keys']:
            set_input_weight('beemizer', '3', 0)
            set_input_weight('beemizer', '4', 0)

        if settings['timer'] != 'none':
            force_setting('beemizer', '0')

        roll_setting('beemizer')
        roll_setting('key_logic_algorithm')
        roll_setting('any_enemy_logic')
        roll_setting('flute_mode')
        roll_setting('swords')
        roll_setting('shufflebosses')
        roll_setting('enemy_damage')
        roll_setting('enemy_health')
        roll_setting('boots_hint')
        roll_setting('restrict_boss_items')
        roll_setting('overworld_map')
        roll_setting('shufflelinks')
        roll_setting('shuffletavern')
        roll_setting('shuffleganon')
        roll_setting('openpyramid')
        roll_setting('experimental')
        roll_setting('algorithm')
        roll_setting('dungeon_counters')
        roll_setting('hints')
        roll_setting('pseudoboots')
        roll_setting('item_functionality')
        roll_setting('progressive')
        roll_setting('accessibility')
        roll_setting('take_any')
        roll_setting('dropshuffle')

        if settings['goal'] in ['triforcehunt', 'ganonhunt']:
            tfh_weights_list = triforcehunt()
            if not tfh_weights_list:
                continue
            random.shuffle(tfh_weights_list)
            cached_score = copy.copy(score)
            for tfh_weights in tfh_weights_list:
                score = copy.copy(cached_score)
                score['length'] = int((tfh_weights[2] * 3 + score['length'])/4)
                score['execution'] += tfh_weights[3]
                score['familiarity'] += tfh_weights[4]
                score['variance'] += tfh_weights[5]
                if within_limits(score):
                    break
            settings['triforce_goal'] = tfh_weights[0]
            settings['triforce_pool'] = tfh_weights[1]
 
        if settings['pseudoboots'] == 1:
            input_weights['startinventory']['Pegasus Boots']['weight'] = 0

        if settings['mode'] == 'standard' and settings['keyshuffle'] == 'universal':
            startinventory.append('Small Key (Universal),Small Key (Universal),Small Key (Universal)')

        # Add items that puts the score within limits
        start_item_options = [item for item in input_weights['startinventory'].keys() if input_weights['startinventory'][item]['weight'] > 0 and item not in startinventory]
        random.shuffle(start_item_options)
        for item in start_item_options:
            item_weights = input_weights['startinventory'][item]
            if len(startinventory) >= args.max_items or within_limits(score):
                break
            if better_than_current(item_weights) and random.random() > 0.40:
                for attr,_,_ in attrs:
                    score[attr] += item_weights[attr]
                startinventory.append(item)

        # Add minimum amount of items and bonus items
        start_item_options = [item for item in start_item_options if item not in startinventory]
        random.shuffle(start_item_options)
        for item in start_item_options:
            item_weights = input_weights['startinventory'][item]
            if len(startinventory) < args.min_items:
                if item_within_limits(item_weights):
                    for attr,_,_ in attrs:
                        score[attr] += item_weights[attr]
                    startinventory.append(item)
            elif len(startinventory) < args.max_items and item_within_limits(item_weights):
                if random.random() < 0.65:
                    break
                for attr,_,_ in attrs:
                    score[attr] += item_weights[attr]
                startinventory.append(item)

        if 'Pegasus Boots' in startinventory:
            settings['boots_hint'] == 'off'

        if startinventory:
            settings['usestartinventory'] = 1
            settings['startinventory'] = ','.join(startinventory)  

        if within_limits(score):
            print_to_stdout(score)
            print_to_stdout('Filler Algorithm: {}'.format(settings['algorithm']))
            print_to_stdout('Boss item restriction: {}'.format(settings['restrict_boss_items']))
            print_to_stdout('Take Any: {}'.format(settings['take_any']))
            print_to_stdout('Pseudoboots: {}'.format('Yes' if settings['pseudoboots'] == 1 else 'No'))
            print_to_stdout('Boots Hint: {}'.format('Yes' if settings['boots_hint'] == 1 else 'No'))
            if 'triforce_pool' in settings:
                print_to_stdout('Extra TF Pool: {}%'.format(round(100*(settings['triforce_pool']/settings['triforce_goal']-1),1)))
            break

    if within_limits(score):
        return settings

def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('-i', help='Path to the points weights file to use for rolling game settings')
    parser.add_argument('-o', help='Output path for the rolled mystery json')
    parser.add_argument('-d', help='Default settings')
    parser.add_argument('--force', help='setting1:option,setting2:option')
    parser.add_argument('--veto', help='setting1:option,setting2:option')
    parser.add_argument('--preset', help='friendly, notslow, complex, ordeal, or chaos')
    parser.add_argument('--min_length', help='-5 to 30', type=int)
    parser.add_argument('--max_length', help='-5 to 30', type=int)
    parser.add_argument('--min_execution', help='-5 to 30', type=int)
    parser.add_argument('--max_execution', help='-5 to 30', type=int)
    parser.add_argument('--min_familiarity', help='-5 to 30', type=int)
    parser.add_argument('--max_familiarity', help='-5 to 30', type=int)
    parser.add_argument('--min_variance', help='-15 to 15', type=int)
    parser.add_argument('--max_variance', help='-15 to 15', type=int)
    parser.add_argument('--min_items', help='', type=int)
    parser.add_argument('--max_items', help='', type=int)
    parser.add_argument('--multi', help='This flag does some minimal balancing for multiworlds', action='store_true')

    args = parser.parse_args()

    weight_file = args.i if args.i else "MMMM_weights.json"
    default_file = args.d if args.d else "MMMM_base.json"
    output_file = args.o if args.o else "MMMM_mystery.json"
    presets = {
        'friendly': {'min_length': -6, 'max_length': 2, 'min_execution': -5, 'max_execution': 3, 'min_familiarity': -5, 'max_familiarity': 5, 'min_variance': -4, 'max_variance': 5, 'min_items': 1, 'max_items': 5},
        'notslow': {'min_length': -2, 'max_length': 5, 'min_execution': -3, 'max_execution': 4, 'min_familiarity': 1, 'max_familiarity': 15, 'min_variance': -5, 'max_variance': 5, 'min_items': 0, 'max_items': 3},
        'complex': {'min_length': 3, 'max_length': 12, 'min_execution': 0, 'max_execution': 6, 'min_familiarity': 8, 'max_familiarity': 20, 'min_variance': -8, 'max_variance': 3, 'min_items': 0, 'max_items': 3},
        'ordeal': {'min_length': 13, 'max_length': 25, 'min_execution': 4, 'max_execution': 11, 'min_familiarity': 15, 'max_familiarity': 30, 'min_variance': -8, 'max_variance': 1, 'min_items': 0, 'max_items': 2},
        'chaos': {'min_length': -100, 'max_length': 100, 'min_execution': -100, 'max_execution': 100, 'min_familiarity': -100, 'max_familiarity': 100, 'min_variance': -100, 'max_variance': 100, 'min_items': 0, 'max_items': 8},
        'volatility': {'min_length': -100, 'max_length': 100, 'min_execution': -100, 'max_execution': 100, 'min_familiarity': -100, 'max_familiarity': 100, 'min_variance': 6, 'max_variance': 100, 'min_items': 0, 'max_items': 8}
    }

    args.preset = args.preset if args.preset in presets else 'friendly'

    preset = presets.get(args.preset, {})
    args.min_length = args.min_length if args.min_length else preset.get('min_length', 0)
    args.max_length = args.max_length if args.max_length else preset.get('max_length', 0)
    args.min_execution = args.min_execution if args.min_execution else preset.get('min_execution', 0)
    args.max_execution = args.max_execution if args.max_execution else preset.get('max_execution', 0)
    args.min_familiarity = args.min_familiarity if args.min_familiarity else preset.get('min_familiarity', 0)
    args.max_familiarity = args.max_familiarity if args.max_familiarity else preset.get('max_familiarity', 0)
    args.min_variance = args.min_variance if args.min_variance else preset.get('min_variance', 0)
    args.max_variance = args.max_variance if args.max_variance else preset.get('max_variance', 0)
    args.min_items = args.min_items if args.min_items else preset.get('min_items', 0)
    args.max_items = args.max_items if args.max_items else preset.get('max_items', 0)

    with open(weight_file, "r", encoding='utf-8') as f:
        input_weights = json.load(f)
    with open(default_file, "r", encoding='utf-8') as f:
        default_settings = json.load(f)

    if args.force:
        forced_settings = args.force.split(',')
        forced_settings = [s.split(':') for s in forced_settings if ':' in s]
        for setting,option in forced_settings:
            if setting in input_weights and option in input_weights[setting]:
                print_to_stdout(f'Forcing {setting}: {option}')
                for key in input_weights[setting]:
                    input_weights[setting][key]['weight'] = 1 if key == option else 0

    if args.veto:
        vetod_settings = args.veto.split(',')
        vetod_settings = [s.split(':') for s in vetod_settings if ':' in s]
        for setting,option in vetod_settings:
            if setting in input_weights and option in input_weights[setting]:
                print_to_stdout(f'Vetoing {setting}: {option}')
                input_weights[setting][option]['weight'] = 0

    if args.multi:
        input_weights['goal']['triforcehunt']['weight'] = 0
        input_weights['goal']['ganonhunt']['weight'] = 0
        input_weights['goal']['completionist']['weight'] = 0
        input_weights['accessibility']['none']['weight'] = 0
        input_weights['mode']['standard']['weight'] = 0
        input_weights['hints']['off']['weight'] = 0
        input_weights['hints']['on']['weight'] = 1
        input_weights['mystery']['on']['weight'] = 0
        input_weights['mystery']['off']['weight'] = 1

    if args.preset in ['friendly', 'notslow']:
        input_weights['door_shuffle']['vanilla']['weight'] = 100
        input_weights['door_shuffle']['basic']['weight'] = 0
        input_weights['door_shuffle']['partitioned']['weight'] = 0
        input_weights['door_shuffle']['crossed']['weight'] = 0

    mystery_settings = make_mystery(input_weights, default_settings, args)
    if not mystery_settings:
        sys.exit("No combination found in time.")

    print_to_stdout('Successfully generated mystery settings: {}'.format(output_file))

    with open(output_file, "w+", encoding='utf-8') as f:
        f.write(json.dumps(mystery_settings, indent=4))

if __name__ == '__main__':
    main()
import json
import argparse
import random
import copy
import sys
import numpy as np

MAX_ATTEMPTS = 1500

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

def print_to_stdout(*a):
    print(*a, file=sys.stdout)

def make_mystery(input_weights, default_settings, args):
    def within_limits(score: dict) -> bool:
        for attr,min,max in attrs:
            score_val = score[attr]
            if score_val < min or score_val > max:
                return False
        return True
   
    def roll_setting(setting_name: str):
        options = list(input_weights[setting_name].keys())
        weights = [input_weights[setting_name][option]['weight'] for option in options]
        if not weights:
            return
        choice = random.choices(options, weights=weights, k=1)[0]
        for attr,_,_ in attrs:
            score[attr] += input_weights[setting_name][choice][attr]

        if setting_name not in ['progressive', 'dungeon_counters', ]:
            if choice == 'on':
                choice = 1
            if choice == 'off':
                choice = 0
        settings[setting_name] = choice

    def force_setting(setting_name: str, choice):
        for key in input_weights[setting_name]:
            if key == choice:
                input_weights[setting_name][key]['weight'] = 1
            else:
                input_weights[setting_name][key]['weight'] = 0

    def determine_pool_size() -> int:
        pool_size = NONDUNGEON
        pool_size += DUNGEON
        pool_size += POTTERY[settings['pottery']]
        if settings['dropshuffle'] == 1:
            pool_size += KEYDROPS
        if settings['shopsanity'] == 1:
            pool_size += SHOPSANITY
        if settings['take_any'] != 'none':
            pool_size += TAKE_ANY
        return pool_size
    
    def determine_mandatory_pool_size() -> int:
        mandatory_pool_size = INVENTORY + MAPSANDCOMPASSES + BIGKEYS + SMALLKEYS + BOSSHEARTS
        if settings['shopsanity'] == 1:
            mandatory_pool_size += SHOPUPGRADES
        if settings['dropshuffle'] == 1:
            mandatory_pool_size += KEYDROPS
        if settings['take_any'] != 'none':
            mandatory_pool_size += TAKE_ANY
        if settings['bow_mode'] in ['retro', 'retro_silvers']:
            mandatory_pool_size += RETRO_ARROWS
        if settings['pottery'] not in ['none', 'cave']:
            mandatory_pool_size += POTTERY['keys']
        return mandatory_pool_size        

    def simulate_tfh(goal:int, pool:int, total:int):
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
        delta = 0
        for attr,min,max in attrs:
            score_val = score[attr] 
            new_val = new_points[attr]
            if score_val < min:
                delta += new_val
            elif score_val > max:
                delta -= new_val
            elif new_val + score_val < min or score_val + new_val > max:
                return False
        return delta > 0

    def item_within_limits(new_points:dict) -> bool:
        for attr,min,max in attrs:
            eval = score[attr] + new_points[attr]
            if eval < min or eval > max:
                return False
        return True 

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
        input_weights['algorithm']['vanilla_fill']['weight'] = 0
        startinventory = []
        score = {}
        for attr,_,_ in attrs:
            score[attr] = 0

        roll_setting('logic')
        if settings['logic'] != 'noglitches':
            input_weights['algorithm']['dungeon_only']['weight'] = 0
            force_setting('pseudoboots', 'off')
            startinventory.append('Pegasus Boots')
            input_weights['startinventory']['Pegasus Boots']['weight'] = 0

        roll_setting('goal')
        if settings['goal'] in ['triforcehunt', 'ganonhunt', 'trinity']:
            input_weights['algorithm']['major_only']['weight'] = 0
        if settings['goal'] == 'ganonhunt':
            force_setting('openpyramid', 'on')
        if settings['goal'] == 'completionist':
            force_setting('accessibility', 'locations')
            force_setting('mystery', 'off')
            force_setting('collection_rate', 'on')
        if settings['goal'] in ('ganon', 'crystals'):
            roll_setting('crystals_ganon')
        if settings['goal'] == 'crystals':
            force_setting('openpyramid', 'on')

        roll_setting('mode')
        if settings['mode'] == 'standard':
            input_weights['boots_hint']['on']['weight'] = input_weights['boots_hint']['off']['weight']
            input_weights['startinventory']['Ocarina']['weight'] = 0
            input_weights['shuffle']['insanity']['weight'] = 0
             
        roll_setting('timer')
        if settings['timer'] != 'none':
            force_setting('shuffleenemies', 'none')
            force_setting('shufflebosses', 'none')

        roll_setting('shuffleenemies')
        if settings['shuffleenemies'] != 'none' and settings['mode'] == 'standard':
            force_setting('swords', 'assured')
        if settings['shuffleenemies'] != 'none':
            input_weights['enemy_health']['hard']['weight'] = 0
            input_weights['enemy_health']['expert']['weight'] = 0

        roll_setting('shuffle')
        if settings['shuffle'] == 'vanilla':
            force_setting('shuffleganon', 'off')
            force_setting('shufflelinks', 'off')
            force_setting('shuffletavern', 'off')
            force_setting('overworld_map', 'default')
            force_setting('take_any', 'none')
        if settings['shuffle'] == 'lean':
            input_weights['pottery']['lottery']['weight'] = 0
            input_weights['pottery']['reduced']['weight'] = 0
            input_weights['pottery']['cave']['weight'] = 0
            input_weights['pottery']['cavekeys']['weight'] = 0
            force_setting('shopsanity', 'off')
        if settings['shuffle'] == 'insanity':
            force_setting('bombbag', 'off')
            startinventory.append('Ocarina')
            input_weights['startinventory']['Ocarina']['weight'] = 0

        if settings['shuffle'] != 'vanilla':
            if settings['goal'] == 'ganonhunt':
                force_setting('shuffleganon', 'off')
                force_setting('openpyramid', 'on')
            else:
                force_setting('shuffleganon', 'on')
                force_setting('openpyramid', 'off')
            if settings['mode'] == 'inverted':
                force_setting('shufflelinks', 'on')
            force_setting('accessibility', 'locations')
            input_weights['take_any']['random']['familiarity'] = 0
            input_weights['take_any']['fixed']['familiarity'] = 0

        if settings['shuffle'] == 'vanilla' and settings['goal'] == 'ganon':
            max_gt = int(settings['crystals_ganon'])
            for key in input_weights['crystals_gt']:
                if int(key) > max_gt:
                    input_weights['crystals_gt'][key]['weight'] = 0
                else:
                    input_weights['crystals_gt'][key]['length'] = 0
                    input_weights['crystals_gt'][key]['execution'] = 0
            roll_setting('crystals_gt')
        elif settings['shuffle'] != 'vanilla' and settings['goal'] == 'ganonhunt' and settings['openpyramid'] == 0:
            settings['crystals_gt'] = "0"
        else:
            settings['crystals_gt'] = str(random.randint(0,7))

        roll_setting('door_shuffle')
        if settings['door_shuffle'] != 'vanilla':
            roll_setting('intensity')
            roll_setting('door_type_mode')
            roll_setting('decoupledoors')
            force_setting('dungeon_counters', 'on')
            input_weights['wild_dungeon_items']['none']['weight'] = 0

        roll_setting('pottery')
        if settings['pottery'] not in ('none', 'cave'):
            force_setting('dungeon_counters', 'on')
            force_setting('dropshuffle', 'on')
        if settings['pottery'] not in ('none', 'cave', 'keys', 'cavekeys') and settings['goal'] not in ['triforcehunt', 'ganonhunt']:
            force_setting('wild_dungeon_items', 'mcsb')
        if settings['pottery'] != 'none':
            settings['colorizepots'] = 1

        roll_setting('wild_dungeon_items')
        if 'm' in settings['wild_dungeon_items'] and 'c' in settings['wild_dungeon_items'] and 's' in settings['wild_dungeon_items'] and 'b' in settings['wild_dungeon_items']:
            force_setting('restrict_boss_items', 'none')
        elif 'm' in settings['wild_dungeon_items'] and 'c' in settings['wild_dungeon_items']:
            input_weights['restrict_boss_items']['mapcompass']['weight'] = 0
        
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
            input_weights['startinventory']['Small Key (Universal),Small Key (Universal),Small Key (Universal)']['weight'] = 0

        roll_setting('bow_mode')
        if settings['bow_mode'] in  ['retro', 'retro_silvers']:
            input_weights['startinventory']['Bow'] = input_weights['startinventory'].pop('Progressive Bow')
            input_weights['startinventory']['Arrow Upgrade (+10)']['weight'] = 0

        roll_setting('difficulty')
        if settings['difficulty'] in ['hard','expert']:
            input_weights['startinventory']['Progressive Armor,Progressive Armor']['weight'] = 0

        roll_setting('bombbag')
        if settings['bombbag'] == 1:
            input_weights['startinventory']['Bomb Upgrade (+10)']['weight'] = 0
            input_weights['startinventory']['Bombs (10)']['weight'] = 0

        roll_setting('shopsanity')

        roll_setting('mystery')
        if (settings['shopsanity'] == 0 and settings['pottery'] == 'none'):
            force_setting('collection_rate', 'off')
        roll_setting('collection_rate')

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
        roll_setting('beemizer')
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

        # Add items that puts the score within limits
        start_item_options = [item for item in input_weights['startinventory'].keys() if input_weights['startinventory'][item]['weight'] > 0 and item not in startinventory]
        random.shuffle(start_item_options)
        for item in start_item_options:
            item_weights = input_weights['startinventory'][item]
            if len(startinventory) >= args.max_items or within_limits(score):
                break
            if better_than_current(item_weights) and random.random() > 0.25:
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
                if random.random() < 0.5:
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
    parser.add_argument('--multi', help='', action='store_true')

    args = parser.parse_args()

    weight_file = args.i if args.i else "MMMM_weights.json"
    default_file = args.d if args.d else "MMMM_base.json"
    output_file = args.o if args.o else "MMMM_mystery.json"

    args.preset = args.preset if args.preset else 'friendly'
    if args.preset == 'friendly':
        args.min_length = args.min_length if args.min_length else -6
        args.max_length = args.max_length if args.max_length else 2
        args.min_execution = args.min_execution if args.min_execution else -5
        args.max_execution = args.max_execution if args.max_execution else 3
        args.min_familiarity = args.min_familiarity if args.min_familiarity else -5
        args.max_familiarity = args.max_familiarity if args.max_familiarity else 5
        args.min_variance = args.min_variance if args.min_variance else -4
        args.max_variance = args.max_variance if args.max_variance else 5
        args.min_items = args.min_items if args.min_items else 1
        args.max_items = args.max_items if args.max_items else 4
    if args.preset == 'notslow':
        args.min_length = args.min_length if args.min_length else -6
        args.max_length = args.max_length if args.max_length else 0
        args.min_execution = args.min_execution if args.min_execution else -5
        args.max_execution = args.max_execution if args.max_execution else 5
        args.min_familiarity = args.min_familiarity if args.min_familiarity else -3
        args.max_familiarity = args.max_familiarity if args.max_familiarity else 15
        args.min_variance = args.min_variance if args.min_variance else -5
        args.max_variance = args.max_variance if args.max_variance else 5
        args.min_items = args.min_items if args.min_items else 0
        args.max_items = args.max_items if args.max_items else 5
    if args.preset == 'complex':
        args.min_length = args.min_length if args.min_length else 3
        args.max_length = args.max_length if args.max_length else 12
        args.min_execution = args.min_execution if args.min_execution else 0
        args.max_execution = args.max_execution if args.max_execution else 6
        args.min_familiarity = args.min_familiarity if args.min_familiarity else 8
        args.max_familiarity = args.max_familiarity if args.max_familiarity else 20
        args.min_variance = args.min_variance if args.min_variance else -8
        args.max_variance = args.max_variance if args.max_variance else 3
        args.min_items = args.min_items if args.min_items else 0
        args.max_items = args.max_items if args.max_items else 3
    if args.preset == 'ordeal':
        args.min_length = args.min_length if args.min_length else 10
        args.max_length = args.max_length if args.max_length else 30
        args.min_execution = args.min_execution if args.min_execution else 4
        args.max_execution = args.max_execution if args.max_execution else 10
        args.min_familiarity = args.min_familiarity if args.min_familiarity else 15
        args.max_familiarity = args.max_familiarity if args.max_familiarity else 30
        args.min_variance = args.min_variance if args.min_variance else -8
        args.max_variance = args.max_variance if args.max_variance else 1
        args.min_items = args.min_items if args.min_items else 0
        args.max_items = args.max_items if args.max_items else 2
    if args.preset == 'chaos':
        args.min_length = args.min_length if args.min_length else -100
        args.max_length = args.max_length if args.max_length else 100
        args.min_execution = args.min_execution if args.min_execution else -100
        args.max_execution = args.max_execution if args.max_execution else 100
        args.min_familiarity = args.min_familiarity if args.min_familiarity else -100
        args.max_familiarity = args.max_familiarity if args.max_familiarity else 100
        args.min_variance = args.min_variance if args.min_variance else -100
        args.max_variance = args.max_variance if args.max_variance else 100
        args.min_items = args.min_items if args.min_items else 0
        args.max_items = args.max_items if args.max_items else 8

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
        input_weights['mystery']['on']['weight'] = 0

    mystery_settings = make_mystery(input_weights, default_settings, args)
    if not mystery_settings:
        sys.exit("No combination found in time.")

    print_to_stdout('Successfully generated mystery settings: {}'.format(output_file))

    with open(output_file, "w+", encoding='utf-8') as f:
        f.write(json.dumps(mystery_settings, indent=4))

if __name__ == '__main__':
    main()
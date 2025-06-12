# character.py

import copy
import logging
import re
from typing import Dict, List, Any, Optional, Tuple

# Define account levels
ACCOUNT_LEVELS = {
    "player": 1,
    "moderator": 50,
    "admin": 100,
    "immortal": 1000
}

# Define the skills for Wanderer class
WANDERER_SKILLS = {
    2: {
        "name": "Quick Slash",
        "description": "A swift attack dealing additional damage.",
        "level_required": 2,
        "cooldown": 5,
        "sp_cost": 10,
        "target_type": "single",
        "effects": [{"type": "damage", "value": 10}]
    },
    4: {
        "name": "Blade Flurry",
        "description": "A flurry of blades that hits all enemies.",
        "level_required": 4,
        "cooldown": 8,
        "sp_cost": 15,
        "target_type": "area",
        "effects": [{"type": "area_damage", "value": 8}]
    },
    6: {
        "name": "Battle Stance",
        "description": "Increase your strength temporarily.",
        "level_required": 6,
        "cooldown": 20,
        "sp_cost": 25,
        "target_type": "self",
        "effects": [{"type": "buff", "stat": "Strength", "value": 5, "duration": 30}]
    }
}

def experience_required_for_next_level(level: int) -> int:
    return 100 + (level - 1) * 50

def check_and_grant_skills(character: Dict) -> None:
    current_level = character.get('level', 1)
    if 'skills' not in character:
        character['skills'] = []

    # Fix: Changed to use skill['name'] instead of skill.get('name')
    character_skills = {skill['name'].lower(): skill for skill in character['skills']}
    
    for level, skill_data in WANDERER_SKILLS.items():
        if current_level >= level and skill_data['name'].lower() not in character_skills:
            new_skill = copy.deepcopy(skill_data)
            character['skills'].append(new_skill)
            logging.info(f"Granted skill '{new_skill['name']}' to character '{character['name']}' for level {level}")

def handle_character_login(character: Dict) -> None:
    ensure_character_compatibility(character)
    check_and_grant_skills(character)

def display_character_sheet(client_socket: Any, character: Dict) -> None:
    ensure_character_compatibility(character)

    current_level = character.get('level', 1)
    current_exp = character.get('experience', 0)
    exp_for_next_level = experience_required_for_next_level(current_level)

    total_stats, gear_bonuses = calculate_total_stats(character)

    RESET = "\033[0m"
    BLUE = "\033[94m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"

    ansi_escape = re.compile(r'\033\[[0-9;]*m')

    def strip_ansi(text: str) -> str:
        return ansi_escape.sub('', text)

    def calc_printable_length(text: str) -> int:
        return len(strip_ansi(text))

    def pad_string(text: str, width: int, align: str = 'left') -> str:
        printable_length = calc_printable_length(text)
        padding = width - printable_length
        if padding < 0:
            text = strip_ansi(text)[:width]
            padding = 0
        if align == 'left':
            return text + ' ' * padding
        elif align == 'right':
            return ' ' * padding + text
        elif align == 'center':
            left_padding = padding // 2
            right_padding = padding - left_padding
            return ' ' * left_padding + text + ' ' * right_padding
        return text

    total_width = 78
    separator = "|"
    col_width = (total_width - len(separator)) // 2

    lines = []

    lines.append("=" * total_width)
    header_title = f"{GREEN}Character Overview{RESET}"
    lines.append(f"{separator}{pad_string(header_title, total_width - 2, 'center')}{separator}")
    lines.append("=" * total_width)

    name_line = f"Name: {character['name']}"
    class_line = f"Class: {character.get('class', 'Wanderer')}"
    name_line = pad_string(name_line, col_width)
    class_line = pad_string(class_line, col_width)
    lines.append(f"{name_line}{class_line}")

    level_line = f"Level: {current_level}"
    exp_line = f"EXP: {current_exp}/{exp_for_next_level}"
    level_line = pad_string(level_line, col_width)
    exp_line = pad_string(exp_line, col_width)
    lines.append(f"{level_line}{exp_line}")

    lines.append("-" * total_width)
    health_power_title = f"{RED}Health{RESET} and {BLUE}Power{RESET}"
    lines.append(f"{separator}{pad_string(health_power_title, total_width - 2, 'center')}{separator}")
    lines.append("-" * total_width)

    hp_text = f"{RED}HP{RESET}: {total_stats['HP']}/{total_stats['Max_HP']}"
    sp_text = f"{YELLOW}SP{RESET}: {total_stats['SP']}/{total_stats['Max_SP']}"
    ap_text = f"{BLUE}AP{RESET}: {total_stats['AP']}/{total_stats['Max_AP']}"
    hp_text = pad_string(hp_text, col_width // 3)
    sp_text = pad_string(sp_text, col_width // 3)
    ap_text = pad_string(ap_text, col_width // 3)
    lines.append(f"{hp_text}{sp_text}{ap_text}")

    lines.append("=" * total_width)
    main_stats_title = "Main Stats"
    equipped_gear_title = "Equipped Gear"
    main_stats_title = pad_string(main_stats_title, col_width, 'center')
    equipped_gear_title = pad_string(equipped_gear_title, col_width, 'center')
    lines.append(f"{main_stats_title}{separator}{equipped_gear_title}")
    lines.append("-" * col_width + "+" + "-" * col_width)

    stats = ["Strength", "Tenacity", "Agility", "Intelligence", "Revel", "Defense"]
    equipment_slots = ["head", "neck", "chest", "waist", "legs", "feet", "hands",
                      "ring1", "ring2", "mainhand", "offhand", "light_source"]

    max_lines = max(len(stats), len(equipment_slots))
    equipment = character.get('equipment', {})

    for i in range(max_lines):
        if i < len(stats):
            stat_name = stats[i]
            base_value = character['base_stats'][stat_name]
            total_value = total_stats[stat_name]
            gear_bonus = gear_bonuses.get(stat_name, 0)
            if gear_bonus > 0:
                stat_value = f"{total_value} {BLUE}(+{gear_bonus}){RESET}"
            else:
                stat_value = f"{total_value}"
            stat_line = f"{stat_name}: {stat_value}"
            stat_line = pad_string(stat_line, col_width)
        else:
            stat_line = ' ' * col_width

        if i < len(equipment_slots):
            slot = equipment_slots[i]
            slot_name = f"{GREEN}{slot.replace('_', ' ').title()}{RESET}:"
            item = equipment.get(slot)
            item_name = item['name'] if item and 'name' in item else 'None'
            equip_line = f"{slot_name} {item_name}"
            equip_line = pad_string(equip_line, col_width)
        else:
            equip_line = ' ' * col_width

        lines.append(f"{stat_line}{separator}{equip_line}")

    lines.append("=" * total_width)

    char_sheet = '\n'.join(lines) + '\n'
    client_socket.sendall(char_sheet.encode())

def calculate_total_stats(character: Dict) -> Tuple[Dict, Dict]:
    stats = character.get('stats', {})
    total_stats = copy.deepcopy(stats)

    gear_bonuses = {
        "Strength": 0,
        "Tenacity": 0,
        "Agility": 0,
        "Intelligence": 0,
        "Revel": 0,
        "Defense": 0,
        "Max_HP": 0,
        "Max_SP": 0,
        "Max_AP": 0
    }

    equipment = character.get('equipment', {})
    for slot, item in equipment.items():
        if item:
            for stat in gear_bonuses.keys():
                bonus = item.get('stats', {}).get(stat, 0)
                gear_bonuses[stat] += bonus
                total_stats[stat] += bonus

    current_stats = character.get('stats', {})
    total_stats['HP'] = min(current_stats.get('HP', total_stats['Max_HP']), total_stats['Max_HP'])
    total_stats['SP'] = min(current_stats.get('SP', total_stats['Max_SP']), total_stats['Max_SP'])
    total_stats['AP'] = min(current_stats.get('AP', total_stats['Max_AP']), total_stats['Max_AP'])

    return total_stats, gear_bonuses

def ensure_character_compatibility(character: Dict) -> Dict:
    required_fields = {
        "name": "",
        "class": "Wanderer",
        "level": 1,
        "account_level": ACCOUNT_LEVELS["player"],
        "stats": {
            "HP": 20,
            "SP": 20,
            "AP": 0,
            "Max_HP": 20,
            "Max_SP": 20,
            "Max_AP": 0,
            "Strength": 5,
            "Tenacity": 5,
            "Agility": 5,
            "Intelligence": 5,
            "Revel": 5,
            "Defense": 0
        },
        "base_stats": {
            "Strength": 5,
            "Tenacity": 5,
            "Agility": 5,
            "Intelligence": 5,
            "Revel": 5,
            "Defense": 0,
            "Max_HP": 20,
            "Max_SP": 20,
            "Max_AP": 0
        },
        "equipment": {
            "head": None,
            "neck": None,
            "chest": None,
            "waist": None,
            "legs": None,
            "feet": None,
            "hands": None,
            "ring1": None,
            "ring2": None,
            "mainhand": None,
            "offhand": None,
            "light_source": None
        },
        "inventory": [],
        "in_combat": False,
        "opponent": None,
        "experience": 0,
        "skills": [],
        "cooldowns": {},
        "active_effects": [],
        "username": "",
        "room": "1",
        "gold": 0
    }

    for key, value in required_fields.items():
        if key not in character:
            character[key] = copy.deepcopy(value)
            logging.debug(f"Added missing field '{key}' with default value.")
        elif isinstance(value, dict):
            for subkey, subvalue in value.items():
                if subkey not in character[key]:
                    character[key][subkey] = subvalue
                    logging.debug(f"Added missing subfield '{subkey}' in '{key}' with default value.")

    return character

def level_up(character: Dict, account_manager: Any) -> bool:
    current_level = character.get('level', 1)
    logging.info(f"Player '{character['name']}' is leveling up from level {current_level}.")

    previous_stats = character['stats'].copy()

    character['stats']['Max_HP'] += 5
    character['stats']['Max_SP'] += 2
    character['stats']['Strength'] += 1
    character['stats']['Tenacity'] += 1
    character['stats']['Agility'] += 1

    logging.info(
        f"Stat increases for {character['name']}: "
        f"HP: {previous_stats['Max_HP']} -> {character['stats']['Max_HP']}, "
        f"SP: {previous_stats['Max_SP']} -> {character['stats']['Max_SP']}, "
        f"Strength: {previous_stats['Strength']} -> {character['stats']['Strength']}, "
        f"Tenacity: {previous_stats['Tenacity']} -> {character['stats']['Tenacity']}, "
        f"Agility: {previous_stats['Agility']} -> {character['stats']['Agility']}"
    )

    character['stats']['HP'] = character['stats']['Max_HP']
    character['stats']['SP'] = character['stats']['Max_SP']

    check_and_grant_skills(character)

    if account_manager.update_character(character['username'], character):
        logging.info(f"Player '{character['name']}' successfully leveled up to {character['level']} and stats updated.")
    else:
        logging.error(f"Failed to save updated stats for player '{character['name']}'. Check the account manager.")

    return True



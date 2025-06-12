from .account_manager import AccountManager
from .character import (
    calculate_total_stats,
    ensure_character_compatibility,
    display_character_sheet
)
from .commands import (
    handle_help,
    handle_look,
    handle_examine,
    handle_inventory,
    handle_get,
    handle_drop,
    handle_destroy_command,
    handle_equip,
    handle_unequip,
    handle_summon_command,
    handle_skills,
    handle_use,
    handle_movement,
    # Add new container-related handlers
    handle_put,
    handle_lock,
    handle_unlock,
    # Add other missing handlers
    handle_skill_use,
    handle_cast,
    handle_eat,
    handle_drink,
    handle_read,
    handle_chat_command,
    cleanup_player,
    grant_skills_on_login
)
from .data_handler import load_json, save_json
from .items import ItemManager
from .mobs import MobManager
from .rooms import RoomManager
from .skills import SkillManager
from .spells import SpellManager  # Add SpellManager import
from .server_handler import GameServer  # Correct import
from .utils import (
    pad_string,
    strip_ansi,
    calc_printable_length
)

# Initialize SkillManager with updated path
skill_manager = SkillManager('game_data/skills.json')
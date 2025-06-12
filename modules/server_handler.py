import socket
import threading
import logging
import time
import random
import copy
from queue import Queue
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import json

from modules.account_manager import AccountManager
from modules.rooms import RoomManager
from modules.items import ItemManager
from modules.mobs import MobManager, MobSpawnManager
from modules.skills import SkillManager # Added SkillManager import
from modules.spells import SpellManager
from modules.effects import EffectType, TargetType, EffectHandler
from modules.commands import handle_command, handle_look
from modules.combat import CombatManager
from modules.character import ensure_character_compatibility
from modules.data_handler import load_json, save_json

# Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    filename='logs/server.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('logs/server.log'),
        logging.StreamHandler()
    ]
)

# Server configuration
HOST = '0.0.0.0'
PORT = 4000
BUFFER_SIZE = 1024
REGEN_INTERVAL = 10  # Regeneration tick interval in seconds
TIME_INCREMENT = 10  # Time increment in seconds (real-time)
SPAWN_CHECK_INTERVAL = 10  # How often to check for spawns (in seconds)
DEFAULT_RESPAWN_TIME = 180  # Default respawn time (3 minutes) if none specified

# Initialize global state
active_characters = {}  # Track currently active characters
active_characters_lock = threading.RLock()
players = []
players_lock = threading.RLock()
current_time = 0  # Time in minutes since midnight (0 = 12:00 AM, 720 = 12:00 PM)
dead_mobs = Queue()  # Thread-safe queue to track dead mobs

# Track mob instances per room
mob_instances = {}
mob_instances_lock = threading.RLock()

# Removed local MobSpawnManager class

# Commented out local MobManager class
# class MobManager:
#     def __init__(self, mobs_file, room_manager):
#         self.mobs_file = mobs_file
#         self.room_manager = room_manager  # Add room_manager as an attribute
#         self.lock = threading.RLock()
#         self.mobs = load_json(mobs_file)
#         self.spawn_manager = None  # Will be set after initialization
#         logging.debug(f"MobManager initialized with mobs: {[mob['name'] for mob in self.mobs]}")
#
#     def set_spawn_manager(self, spawn_manager):
#         """Set the spawn manager instance."""
#         self.spawn_manager = spawn_manager
#         logging.debug("SpawnManager connected to MobManager")
#
#     def get_mob_by_vnum(self, vnum):
#         """Get a mob template by its VNUM."""
#         try:
#             vnum_str = str(vnum)  # Convert vnum to string for comparison
#             with self.lock:
#                 for mob in self.mobs:
#                     if str(mob.get('vnum')) == vnum_str:
#                         return copy.deepcopy(mob)  # Return a copy so original isn't modified
#             logging.error(f"Mob with vnum {vnum} not found")
#             return None
#         except Exception as e:
#             logging.error(f"Error retrieving mob with vnum {vnum}: {e}")
#             return None
#
#     def spawn_mob_in_room(self, mob_vnum: str, room_vnum: str) -> bool:
#         """Spawn a mob in a specific room."""
#         try:
#             # Get the mob template
#             mob_template = self.get_mob_by_vnum(mob_vnum)
#             if not mob_template:
#                 logging.error(f"No template found for mob {mob_vnum}")
#                 return False
#
#             # Create instance ID for the mob
#             instance_id = f"{mob_vnum}_{int(time.time())}_{random.randint(1000, 9999)}"
#
#             # Create a copy of the template for this instance
#             mob_instance = copy.deepcopy(mob_template)
#             mob_instance['instance_id'] = instance_id
#             mob_instance['is_template'] = False
#             mob_instance['room_vnum'] = room_vnum
#
#             # Add to room
#             success = self.room_manager.add_mob_to_room(room_vnum, mob_instance)
#             if success:
#                 logging.info(f"Spawned mob {mob_vnum} in room {room_vnum} with ID {instance_id}")
#                 return True
#
#             return False
#         except Exception as e:
#             logging.error(f"Error spawning mob: {e}")
#             return False

def initialize_managers():
    """Initialize all game managers in the correct sequence."""
    try:
        logging.debug("Initializing game managers...")

        account_manager = AccountManager(
            accounts_file='game_data/accounts.json',
            characters_file='game_data/characters.json'
        )

        room_manager = RoomManager(rooms_file='game_data/rooms.json')

        mob_manager = MobManager(
            mobs_file='game_data/mobs.json',
            room_manager=room_manager
        )

        spawn_manager = MobSpawnManager(mob_manager, room_manager)

        mob_manager.spawn_manager = spawn_manager

        item_manager = ItemManager(
            items_file='game_data/items.json',
            weapons_file='game_data/weapons.json',
            armors_file='game_data/armor.json',
            consumables_file='game_data/consumables.json',
            containers_file='game_data/containers.json',
            currencies_file='game_data/currencies.json',
            corpses_file='game_data/corpses.json'
        )

        effect_handler = EffectHandler()
        combat_manager = CombatManager(effect_handler, mob_manager)

        skill_manager = SkillManager(skills_file='game_data/skills.json')
        spell_manager = SpellManager(spells_file='game_data/spells.json')

        spawn_manager.start()

        logging.info("All managers initialized successfully.")
        return (
            account_manager, room_manager, item_manager,
            mob_manager, combat_manager, skill_manager,
            spell_manager, spawn_manager
        )

    except Exception as e:
        logging.critical(f"Failed to initialize managers: {e}")
        raise SystemExit("Critical error during initialization. Check logs for details.")

(
    account_manager,
    room_manager,
    item_manager,
    mob_manager,
    combat_manager,
    skill_manager,
    spell_manager,
    spawn_manager
) = initialize_managers()

def regenerate_character_stats(character: Dict) -> None:
    try:
        if not character or character.get('in_combat', False):
            return
        stats = character.get('stats', {})
        if not stats:
            return

        updated = False
        max_hp = stats.get('Max_HP', 100)
        current_hp = stats.get('HP', 0)
        if current_hp < max_hp:
            regen_amount = max(1, int(max_hp * 0.01))
            stats['HP'] = min(max_hp, current_hp + regen_amount)
            updated = True
            logging.debug(f"Character '{character['name']}' HP regenerated: {current_hp} -> {stats['HP']}")

        max_sp = stats.get('Max_SP', 50)
        current_sp = stats.get('SP', 0)
        if current_sp < max_sp:
            regen_amount = max(1, int(max_sp * 0.01))
            stats['SP'] = min(max_sp, current_sp + regen_amount)
            updated = True
            logging.debug(f"Character '{character['name']}' SP regenerated: {current_sp} -> {stats['SP']}")

        max_ap = stats.get('Max_AP', 30)
        current_ap = stats.get('AP', 0)
        if current_ap < max_ap:
            regen_amount = max(1, int(max_ap * 0.01))
            stats['AP'] = min(max_ap, current_ap + regen_amount)
            updated = True
            logging.debug(f"Character '{character['name']}' AP regenerated: {current_ap} -> {stats['AP']}")

        if updated:
            character['stats'] = stats
    except Exception as e:
        logging.error(f"Error regenerating stats for character {character.get('name', 'Unknown')}: {e}")

def regeneration_loop():
    global current_time
    while True:
        try:
            with active_characters_lock:
                for username, char_data in list(active_characters.items()): # Iterate over a copy
                    character = char_data.get('character')
                    if character and not character.get('in_combat', False):
                        regenerate_character_stats(character)

            current_time += TIME_INCREMENT
            if current_time >= 1440:
                current_time = 0

            time.sleep(REGEN_INTERVAL)
        except Exception as e:
            logging.error(f"Error in regeneration loop: {e}")
            time.sleep(REGEN_INTERVAL)

def add_active_character(username: str, character: Dict) -> None:
    with active_characters_lock:
        active_characters[username] = {
            'character': character,
            'last_update': time.time()
        }
        logging.debug(f"Added character '{character['name']}' to active characters")

def remove_active_character(username: str) -> None:
    with active_characters_lock:
        if username in active_characters:
            del active_characters[username]
            logging.debug(f"Removed character for username '{username}' from active characters")

def add_player(player_dict: Dict, players_list: List, lock: threading.RLock) -> None:
    with lock:
        if not any(p['username'] == player_dict['username'] for p in players_list):
            players_list.append(player_dict)
            add_active_character(player_dict['username'], player_dict['character'])
            logging.debug(f"Added player '{player_dict['username']}' to players list.")
        else:
            logging.warning(f"Player '{player_dict['username']}' is already connected.")

def remove_player(username: str, players_list: List, lock: threading.RLock) -> None:
    with lock:
        initial_count = len(players_list)
        players_list[:] = [p for p in players_list if p['username'] != username]
        remove_active_character(username)
        if len(players_list) < initial_count:
            logging.debug(f"Removed player '{username}' from players list.")
        else:
            logging.warning(f"Player '{username}' not found in players list.")

def receive_input(client_socket: socket.socket) -> Optional[str]:
    buffer = ''
    try:
        while True:
            data = client_socket.recv(BUFFER_SIZE).decode()
            if not data:
                logging.debug("Client disconnected during input.")
                return None
            buffer += data
            if '\n' in buffer:
                complete_input, buffer = buffer.split('\n', 1)
                return complete_input.strip()
    except Exception as e:
        logging.error(f"Error receiving input: {e}")
        return None

def handle_login(client_socket: socket.socket, username: str) -> tuple[bool, Optional[str], Optional[Dict]]:
    try:
        client_socket.sendall(b'Enter your password: ')
        password = receive_input(client_socket)
        if not password:
            return False, None, None

        if account_manager.validate_login(username, password):
            chosen_char = account_manager.select_character(username, client_socket)
            if chosen_char:
                ensure_character_compatibility(chosen_char)
                client_socket.sendall(f"Welcome back, {chosen_char['name']}!\n".encode())
                handle_look(
                    chosen_char,
                    client_socket,
                    room_manager,
                    item_manager,
                    mob_manager,
                    account_manager
                )
                return True, username, chosen_char
        client_socket.sendall(b"Invalid login.\n")
        return False, None, None
    except Exception as e:
        logging.error(f"Error during login process: {e}")
        return False, None, None

def game_loop(client_socket: socket.socket, username: str, character: Dict, players_list: List, player_dict: Dict) -> None:
    try:
        while True:
            if not character.get('room'):
                character['room'] = "1"
                account_manager.update_character(username, character)

            client_socket.sendall(b"> ")
            command = receive_input(client_socket)

            if not command or command.lower() in ['exit', 'quit']:
                client_socket.sendall(b"Goodbye!\n")
                break

            handle_command(
                command=command,
                character=character,
                username=username,
                client_socket=client_socket,
                room_manager=room_manager,
                item_manager=item_manager,
                mob_manager=mob_manager,
                account_manager=account_manager,
                skill_manager=skill_manager,
                spell_manager=spell_manager,
                combat_manager=combat_manager,
                user_role="admin" if character.get('account_level', 1) >= 100 else "player"
            )
    except Exception as e:
        logging.error(f"Error in game loop for '{username}': {e}")
        client_socket.sendall(b"An error occurred. Disconnecting.\n")
    finally:
        cleanup_player_session(username, character)

def cleanup_player_session(username: str, character: Dict) -> None:
    try:
        if character and username:
            room_vnum = character.get('room')
            if room_vnum:
                room_manager.remove_player_from_room(room_vnum, username)
                logging.debug(f"Removed player '{username}' from room {room_vnum}")

            account_manager.remove_connected_client(username)
            remove_player(username, players, players_lock)

            account_manager.update_character(username, character)
            logging.info(f"Successfully cleaned up session for player '{username}'")
    except Exception as e:
        logging.error(f"Error cleaning up session for '{username}': {e}")

def handle_client(client_socket: socket.socket, addr: tuple) -> None:
    logging.info(f"New connection from {addr}")
    username = None
    chosen_char = None

    try:
        client_socket.sendall(
            b'Welcome to STAIR Mud! Fantasy RPG Server by Cody Brown and his friend OpenAI ChatGPT\n'
        )

        while True:
            client_socket.sendall(b'Please enter your account name or type "New Account": ')
            account_choice = receive_input(client_socket)
            if not account_choice:
                break

            if account_choice.lower() == "new account":
                client_socket.sendall(b'Enter your desired account name: ')
                new_username = receive_input(client_socket)
                if not new_username:
                    break
                new_username = new_username.lower()
                if account_manager.username_exists(new_username):
                    client_socket.sendall(b'Account already exists. Try again.\n')
                    continue

                client_socket.sendall(b'Enter your password: ')
                password = receive_input(client_socket)
                if not password:
                    break

                success, message = account_manager.create_account(new_username, password)
                if success:
                    client_socket.sendall(b'Account created successfully! Please log in.\n')
                else:
                    client_socket.sendall(f'{message}\n'.encode())
                continue

            if account_manager.username_exists(account_choice.lower()):
                login_success, temp_username, temp_char = handle_login(client_socket, account_choice.lower())
                if login_success and temp_username and temp_char:
                    username = temp_username
                    chosen_char = temp_char
                    player_dict = {
                        "name": chosen_char['name'],
                        "room": chosen_char['room'],
                        "socket": client_socket,
                        "username": username,
                        "character": chosen_char,
                    }
                    add_player(player_dict, players, players_lock)
                    account_manager.add_connected_client(username, client_socket)
                    room_manager.add_player_to_room(chosen_char['room'], username, chosen_char['name'])

                    game_loop(client_socket, username, chosen_char, players, player_dict)
                    break
            else:
                client_socket.sendall(b"Account does not exist.\n")


    except Exception as e:
        logging.error(f"Error handling client {addr}: {e}")
    finally:
        if username and chosen_char:
            cleanup_player_session(username, chosen_char)
        client_socket.close()

class GameServer:
    def __init__(self, host: str, port: int, mob_manager: MobManager, spawn_manager: MobSpawnManager):
        self.host = host
        self.port = port
        self.mob_manager = mob_manager
        self.spawn_manager = spawn_manager
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = False
        self.regeneration_thread = None
        self.file_paths = {
            "Room": 'game_data/rooms.json',
            "Mob": 'game_data/mobs.json'
        }
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logging.info(f"Server bound to {self.host}:{self.port}")
        except Exception as e:
            logging.critical(f"Failed to bind server socket: {e}")
            raise

    def start_regeneration(self):
        self.regeneration_thread = threading.Thread(target=regeneration_loop, daemon=True)
        self.regeneration_thread.start()
        logging.info("Started regeneration thread")

    def initialize_game_state(self):
        try:
            with players_lock:
                players.clear()
            with active_characters_lock:
                active_characters.clear()
            room_manager.initialize_rooms()
            self.clean_mob_instances()
            self.initialize_mobs()
            logging.info("Game state initialized successfully")
            return True
        except Exception as e:
            logging.critical(f"Failed to initialize game state: {e}")
            return False

    def clean_mob_instances(self):
        try:
            with open(self.file_paths["Room"], 'r') as f:
                rooms_data = json.load(f)
            for room_data in rooms_data:
                room_data['mobs'] = [
                    mob for mob in room_data.get('mobs', [])
                    if mob.get('is_template', False)
                ]
            with open(self.file_paths["Room"], 'w') as f:
                json.dump(rooms_data, f, indent=4)
            logging.info("Cleaned all mob instances from rooms")
        except Exception as e:
            logging.error(f"Error cleaning mob instances: {e}")

    def initialize_mobs(self):
        try:
            logging.info("Mob initialization handled by MobSpawnManager.")
            if self.spawn_manager and not self.spawn_manager.running:
                 self.spawn_manager.start()
            return True
        except Exception as e:
            logging.error(f"Error initializing mobs: {e}")

    def start(self):
        if not self.initialize_game_state():
            logging.critical("Failed to initialize game state. Server startup aborted.")
            return

        self.running = True
        self.start_regeneration()

        logging.info("Starting game server and accepting connections...")
        try:
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                    logging.debug(f"Started client thread {client_thread.name} for {addr}")
                except socket.error as e:
                    if self.running:
                        logging.error(f"Socket error accepting client: {e}")
                except Exception as e:
                    if self.running:
                        logging.error(f"Error accepting client connection: {e}")
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt, initiating shutdown...")
        except Exception as e:
            logging.critical(f"Critical server error: {e}")
        finally:
            self.stop()

    def stop(self):
        try:
            self.running = False
            if self.spawn_manager:
                self.spawn_manager.stop()

            with players_lock:
                for player in players:
                    try:
                        if player.get('socket'):
                            player['socket'].close()
                    except Exception as e:
                        logging.error(f"Error closing client socket: {e}")
                players.clear()

            with active_characters_lock:
                active_characters.clear()

            try:
                self.server_socket.close()
            except Exception as e:
                logging.error(f"Error closing server socket: {e}")

            logging.info("Server shutdown complete")
        except Exception as e:
            logging.critical(f"Error during server shutdown: {e}")

def initialize_logging():
    try:
        Path('logs').mkdir(exist_ok=True)
        logging.basicConfig(
            filename='logs/server.log',
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler('logs/server.log'),
                logging.StreamHandler()
            ]
        )
        logging.info("Logging initialized")
        return True
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        return False

def main():
    if not initialize_logging():
        print("Failed to initialize logging. Aborting startup.")
        return

    try:
        logging.info("Starting STAIR MUD server...")
        Path('game_data').mkdir(exist_ok=True)

        _, _, _, mob_mgr, _, skill_mgr, _, sp_mgr = initialize_managers() # Ensure skill_manager is unpacked if needed locally, or remove if not

        server = GameServer(HOST, PORT, mob_mgr, sp_mgr)
        server.start()
    except KeyboardInterrupt:
        logging.info("Server shutdown initiated by user.")
    except Exception as e:
        logging.critical(f"Critical error during server execution: {e}")
    finally:
        logging.info("Server shutdown complete.")

if __name__ == '__main__':
    main()

[end of modules/server_handler.py]

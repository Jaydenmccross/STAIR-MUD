
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
from modules.mobs import MobManager
from modules.skills import SkillManager
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

class MobSpawnManager:
    """Manages mob spawning, respawning, and instance tracking."""
    
    def __init__(self, mob_manager: Any, room_manager: Any):
        self.mob_manager = mob_manager
        self.room_manager = room_manager
        self.running = True
        self.spawn_thread = None
        self.processing_threads = set()
        self.lock = threading.RLock()
        
        # Initialize tracking dictionaries
        self.mob_counts = {}  # {room_vnum: {mob_vnum: current_count}}
        self.mob_templates = {}  # {room_vnum: {mob_vnum: template_data}}
        self.respawn_queue = Queue()
        
        # Load initial mob counts and templates
        self.load_initial_state()

    def load_initial_state(self):
        """Load initial mob counts and templates from rooms."""
        try:
            rooms = self.room_manager.get_all_rooms()
            for room in rooms:
                room_vnum = str(room.get('vnum'))
                if not room_vnum:
                    continue

                # Initialize room in tracking dictionaries
                if room_vnum not in self.mob_counts:
                    self.mob_counts[room_vnum] = {}
                if room_vnum not in self.mob_templates:
                    self.mob_templates[room_vnum] = {}

                # Process mobs in room
                for mob in room.get('mobs', []):
                    mob_vnum = str(mob.get('vnum'))
                    if mob.get('is_template', False):
                        # Store template
                        self.mob_templates[room_vnum][mob_vnum] = mob
                    else:
                        # Count instance
                        if mob_vnum not in self.mob_counts[room_vnum]:
                            self.mob_counts[room_vnum][mob_vnum] = 0
                        self.mob_counts[room_vnum][mob_vnum] += 1

            logging.info("Loaded initial mob state")
        except Exception as e:
            logging.error(f"Error loading initial mob state: {e}")
    
    def start(self):
        """Start the spawn manager thread."""
        self.spawn_thread = threading.Thread(target=self._spawn_loop, daemon=True)
        self.spawn_thread.start()
        logging.info("Started mob spawn manager")
        
    def _spawn_loop(self):
        """Main loop for processing spawns and respawns."""
        while self.running:
            try:
                # Process respawn queue
                while not self.respawn_queue.empty():
                    respawn_data = self.respawn_queue.get_nowait()
                    self._handle_respawn(respawn_data)
                
                # Check and maintain spawn counts
                self._maintain_spawn_counts()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logging.error(f"Error in spawn loop: {e}")
                time.sleep(10)  # Keep trying even if there's an error
    
    def _maintain_spawn_counts(self):
        """Ensure rooms maintain their desired mob quantities."""
        with self.lock:
            try:
                rooms = self.room_manager.get_all_rooms()
                for room in rooms:
                    room_vnum = str(room.get('vnum'))
                    
                    # Check each mob template in the room
                    for mob in room.get('mobs', []):
                        if mob.get('is_template', False):  # Only process templates
                            mob_vnum = str(mob.get('vnum'))
                            desired_count = int(mob.get('quantity', 1))
                            max_instances = int(mob.get('max_instances', 1))
                            
                            # Count current instances (excluding template)
                            current_count = sum(
                                1 for m in room.get('mobs', [])
                                if str(m.get('vnum')) == mob_vnum 
                                and not m.get('is_template', False)
                            )
                            
                            # Update our tracking
                            if room_vnum not in self.mob_counts:
                                self.mob_counts[room_vnum] = {}
                            self.mob_counts[room_vnum][mob_vnum] = current_count
                            
                            # Spawn more if needed and possible
                            needed = min(desired_count - current_count, max_instances - current_count)
                            if needed > 0:
                                for _ in range(needed):
                                    self._spawn_mob_instance(room_vnum, mob)
                                    if room_vnum in self.mob_counts and mob_vnum in self.mob_counts[room_vnum]:
                                        self.mob_counts[room_vnum][mob_vnum] += 1
                                    logging.debug(f"Spawned mob {mob_vnum} in room {room_vnum}. Current count: {self.mob_counts[room_vnum][mob_vnum]}")
                                    
            except Exception as e:
                logging.error(f"Error maintaining spawn counts: {e}")
    
    def _count_mob_instances(self, room_vnum: str, mob_vnum: str) -> int:
        """Count current instances of a specific mob in a room."""
        try:
            room = self.room_manager.get_room(room_vnum)
            if not room:
                return 0
            
            return sum(
                1 for mob in room.get('mobs', [])
                if str(mob.get('vnum')) == mob_vnum and not mob.get('is_template', False)
            )
        except Exception as e:
            logging.error(f"Error counting mob instances: {e}")
            return 0
    
    def _spawn_mob_instance(self, room_vnum: str, template: Dict) -> bool:
        """Spawn a new instance of a mob from its template."""
        try:
            mob_vnum = str(template.get('vnum'))
            
            # Get base mob data
            base_mob = self.mob_manager.get_mob_by_vnum(mob_vnum)
            if not base_mob:
                logging.error(f"No base mob found for vnum {mob_vnum}")
                return False
            
            # Create unique instance ID
            instance_id = f"{mob_vnum}_{int(time.time())}_{random.randint(1000, 9999)}"
            
            # Create instance from template
            mob_instance = {
                **base_mob,  # Base mob data
                'instance_id': instance_id,
                'is_template': False,
                'is_aggressive': template.get('aggressive', False),
                'room_vnum': room_vnum
            }
            
            # Add to room
            success = self.room_manager.add_mob_to_room(room_vnum, mob_instance)
            if success:
                logging.info(f"Spawned mob {mob_vnum} in room {room_vnum} with ID {instance_id}")
                return True
                
            return False
            
        except Exception as e:
            logging.error(f"Error spawning mob instance: {e}")
            return False

    def _handle_respawn(self, respawn_data: Dict):
        """Process a queued respawn with proper instance tracking."""
        try:
            # Check if it's time to respawn
            if time.time() < respawn_data['respawn_time']:
                # Put it back in the queue if not ready
                self.respawn_queue.put(respawn_data)
                return

            room_vnum = str(respawn_data['room_vnum'])
            mob_vnum = str(respawn_data['mob_vnum'])
            template = respawn_data['template']

            with self.lock:
                # Check instance limits
                current_count = self.mob_counts.get(room_vnum, {}).get(mob_vnum, 0)
                max_instances = int(template.get('max_instances', 1))

                if current_count >= max_instances:
                    logging.info(f"Skipped respawn of mob {mob_vnum} in room {room_vnum}: at max instances ({current_count}/{max_instances})")
                    return

                # Create new instance
                if self._spawn_mob_instance(room_vnum, template):
                    # Update count
                    if room_vnum not in self.mob_counts:
                        self.mob_counts[room_vnum] = {}
                    if mob_vnum not in self.mob_counts[room_vnum]:
                        self.mob_counts[room_vnum][mob_vnum] = 0
                    self.mob_counts[room_vnum][mob_vnum] += 1

        except Exception as e:
            logging.error(f"Error handling respawn: {e}")
    
    def queue_respawn(self, mob_data: Dict):
        """Queue a mob for respawn."""
        try:
            # Get template from the room
            room = self.room_manager.get_room(mob_data.get('room_vnum'))
            if not room:
                logging.error(f"Room {mob_data.get('room_vnum')} not found for respawn")
                return False
            
            template = next(
                (mob for mob in room.get('mobs', [])
                 if mob.get('is_template', True) and str(mob.get('vnum')) == str(mob_data.get('vnum'))),
                None
            )
            
            if not template:
                logging.error(f"No template found for mob {mob_data.get('vnum')} in room {mob_data.get('room_vnum')}")
                return False
            
            # Add to respawn queue with delay
            respawn_time = template.get('respawn_time', 300)  # Default 5 minutes
            respawn_data = {
                'mob_vnum': str(mob_data.get('vnum')),
                'room_vnum': str(mob_data.get('room_vnum')),
                'template': template,
                'respawn_time': time.time() + respawn_time
            }
            
            self.respawn_queue.put(respawn_data)
            logging.info(f"Queued mob {mob_data.get('vnum')} for respawn in {respawn_time} seconds")
            return True
            
        except Exception as e:
            logging.error(f"Error queuing mob respawn: {e}")
            return False

    def handle_mob_death(self, mob_data: Dict):
        """Handle mob death and queue respawn if appropriate."""
        try:
            room_vnum = str(mob_data.get('room_vnum'))
            mob_vnum = str(mob_data.get('vnum'))
            instance_id = mob_data.get('instance_id')

            if not instance_id or mob_data.get('is_template', False):
                return

            with self.lock:
                # Update count
                if room_vnum in self.mob_counts and mob_vnum in self.mob_counts[room_vnum]:
                    self.mob_counts[room_vnum][mob_vnum] = max(0, self.mob_counts[room_vnum][mob_vnum] - 1)

                # Get template for respawn
                template = self.mob_templates.get(room_vnum, {}).get(mob_vnum)
                if template:
                    respawn_time = int(template.get('respawn_time', 300))
                    # Queue respawn
                    respawn_data = {
                        'mob_vnum': mob_vnum,
                        'room_vnum': room_vnum,
                        'template': template,
                        'respawn_time': time.time() + respawn_time
                    }
                    self.respawn_queue.put(respawn_data)
                    logging.info(f"Queued mob {mob_vnum} for respawn in {respawn_time} seconds")

        except Exception as e:
            logging.error(f"Error handling mob death: {e}")

    def stop(self):
        """Stop the spawn manager cleanly."""
        self.running = False
        if self.spawn_thread:
            self.spawn_thread.join(timeout=1.0)
        logging.info("Stopped mob spawn manager")

class MobManager:
    def __init__(self, mobs_file, room_manager):
        self.mobs_file = mobs_file
        self.room_manager = room_manager  # Add room_manager as an attribute
        self.lock = threading.RLock()
        self.mobs = load_json(mobs_file)
        self.spawn_manager = None  # Will be set after initialization
        logging.debug(f"MobManager initialized with mobs: {[mob['name'] for mob in self.mobs]}")

    def set_spawn_manager(self, spawn_manager):
        """Set the spawn manager instance."""
        self.spawn_manager = spawn_manager
        logging.debug("SpawnManager connected to MobManager")

    def get_mob_by_vnum(self, vnum):
        """Get a mob template by its VNUM."""
        try:
            vnum_str = str(vnum)  # Convert vnum to string for comparison
            with self.lock:
                for mob in self.mobs:
                    if str(mob.get('vnum')) == vnum_str:
                        return copy.deepcopy(mob)  # Return a copy so original isn't modified
            logging.error(f"Mob with vnum {vnum} not found")
            return None
        except Exception as e:
            logging.error(f"Error retrieving mob with vnum {vnum}: {e}")
            return None

    def spawn_mob_in_room(self, mob_vnum: str, room_vnum: str) -> bool:
        """Spawn a mob in a specific room."""
        try:
            # Get the mob template
            mob_template = self.get_mob_by_vnum(mob_vnum)
            if not mob_template:
                logging.error(f"No template found for mob {mob_vnum}")
                return False

            # Create instance ID for the mob
            instance_id = f"{mob_vnum}_{int(time.time())}_{random.randint(1000, 9999)}"
            
            # Create a copy of the template for this instance
            mob_instance = copy.deepcopy(mob_template)
            mob_instance['instance_id'] = instance_id
            mob_instance['is_template'] = False
            mob_instance['room_vnum'] = room_vnum

            # Add to room
            success = self.room_manager.add_mob_to_room(room_vnum, mob_instance)
            if success:
                logging.info(f"Spawned mob {mob_vnum} in room {room_vnum} with ID {instance_id}")
                return True

            return False
        except Exception as e:
            logging.error(f"Error spawning mob: {e}")
            return False

def initialize_managers():
    """Initialize all game managers in the correct sequence."""
    try:
        logging.debug("Initializing game managers...")
        
        # Initialize account manager first
        account_manager = AccountManager(
            accounts_file='game_data/accounts.json',
            characters_file='game_data/characters.json'
        )
        
        # Initialize room manager
        room_manager = RoomManager(rooms_file='game_data/rooms.json')
        
        # Initialize MobManager with room_manager
        mob_manager = MobManager(
            mobs_file='game_data/mobs.json',
            room_manager=room_manager
        )
        
        # Create and start SpawnManager
        spawn_manager = MobSpawnManager(mob_manager, room_manager)
        
        # Connect spawn_manager to mob_manager
        mob_manager.spawn_manager = spawn_manager
        
        # Initialize remaining managers
        item_manager = ItemManager(
            items_file='game_data/items.json',
            weapons_file='game_data/weapons.json',
            armors_file='game_data/armor.json',
            consumables_file='game_data/consumables.json',
            containers_file='game_data/containers.json',
            currencies_file='game_data/currencies.json',
            corpses_file='game_data/corpses.json'
        )

        # Create effect handler and combat manager
        effect_handler = EffectHandler()
        combat_manager = CombatManager(effect_handler, mob_manager)
        
        skill_manager = SkillManager(skills_file='game_data/skills.json')
        spell_manager = SpellManager(spells_file='game_data/spells.json')
        
        # Start the spawn manager after everything is initialized
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

# Initialize all managers
(
    account_manager,
    room_manager,
    item_manager,
    mob_manager,
    combat_manager,
    skill_manager,
    spell_manager,
    spawn_manager  # Added this line
) = initialize_managers()

def regenerate_character_stats(character: Dict) -> None:
    """
    Regenerate character stats when out of combat.
    Returns True if stats were updated, False otherwise.
    """
    try:
        if not character or character.get('in_combat', False):
            return False

        stats = character.get('stats', {})
        if not stats:
            return False

        updated = False
        
        # HP regeneration
        max_hp = stats.get('Max_HP', 100)
        current_hp = stats.get('HP', 0)
        if current_hp < max_hp:
            regen_amount = max(1, int(max_hp * 0.01))  # 1% of max HP, minimum 1
            stats['HP'] = min(max_hp, current_hp + regen_amount)
            updated = True
            logging.debug(f"Character '{character['name']}' HP regenerated: {current_hp} -> {stats['HP']}")

        # SP regeneration
        max_sp = stats.get('Max_SP', 50)
        current_sp = stats.get('SP', 0)
        if current_sp < max_sp:
            regen_amount = max(1, int(max_sp * 0.01))  # 1% of max SP, minimum 1
            stats['SP'] = min(max_sp, current_sp + regen_amount)
            updated = True
            logging.debug(f"Character '{character['name']}' SP regenerated: {current_sp} -> {stats['SP']}")

        # AP regeneration
        max_ap = stats.get('Max_AP', 30)
        current_ap = stats.get('AP', 0)
        if current_ap < max_ap:
            regen_amount = max(1, int(max_ap * 0.01))  # 1% of max AP, minimum 1
            stats['AP'] = min(max_ap, current_ap + regen_amount)
            updated = True
            logging.debug(f"Character '{character['name']}' AP regenerated: {current_ap} -> {stats['AP']}")

        if updated:
            character['stats'] = stats
            return True

        return False

    except Exception as e:
        logging.error(f"Error regenerating stats for character {character.get('name', 'Unknown')}: {e}")
        return False

def regeneration_loop():
    """
    Main regeneration loop that runs in a separate thread.
    Updates stats for all active characters.
    """
    global current_time
    while True:
        try:
            with active_characters_lock:
                for username, char_data in active_characters.items():
                    character = char_data.get('character')
                    if character and not character.get('in_combat', False):
                        if regenerate_character_stats(character):
                            # Only update if stats actually changed
                            account_manager.update_character(username, character)
                            logging.debug(f"Updated stats for character '{character['name']}'")
            
            # Increment time
            current_time += TIME_INCREMENT
            if current_time >= 1440:  # 1440 minutes in a day
                current_time = 0
            
            time.sleep(REGEN_INTERVAL)
            
        except Exception as e:
            logging.error(f"Error in regeneration loop: {e}")
            time.sleep(REGEN_INTERVAL)  # Keep the loop going even if there's an error

def add_active_character(username: str, character: Dict) -> None:
    """Add a character to the active characters list."""
    with active_characters_lock:
        active_characters[username] = {
            'character': character,
            'last_update': time.time()
        }
        logging.debug(f"Added character '{character['name']}' to active characters")

def remove_active_character(username: str) -> None:
    """Remove a character from the active characters list."""
    with active_characters_lock:
        if username in active_characters:
            del active_characters[username]
            logging.debug(f"Removed character for username '{username}' from active characters")

def add_player(player_dict: Dict, players: List, players_lock: threading.RLock) -> None:
    """Add a player to the active players list."""
    with players_lock:
        if not any(p['username'] == player_dict['username'] for p in players):
            players.append(player_dict)
            # Also add to active characters for regeneration
            add_active_character(player_dict['username'], player_dict['character'])
            logging.debug(f"Added player '{player_dict['username']}' to players list.")
        else:
            logging.warning(f"Player '{player_dict['username']}' is already connected.")

def remove_player(username: str, players: List, players_lock: threading.RLock) -> None:
    """Remove a player from the active players list."""
    with players_lock:
        initial_count = len(players)
        players[:] = [p for p in players if p['username'] != username]
        # Also remove from active characters
        remove_active_character(username)
        if len(players) < initial_count:
            logging.debug(f"Removed player '{username}' from players list.")
        else:
            logging.warning(f"Player '{username}' not found in players list.")

def receive_input(client_socket: socket.socket) -> Optional[str]:
    """
    Receive input from client socket with proper buffering.
    Returns None if connection is lost.
    """
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
    """Handle player login process and character selection."""
    try:
        client_socket.sendall(b'Enter your password: ')
        password = receive_input(client_socket)
        if not password:
            return False, None, None

        if account_manager.validate_login(username, password):
            chosen_char = account_manager.select_character(username, client_socket)
            if chosen_char:
                # Ensure character data is compatible with current game version
                ensure_character_compatibility(chosen_char)
                
                client_socket.sendall(f"Welcome back, {chosen_char['name']}!\n".encode())
                
                # Show initial room description
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

def game_loop(client_socket: socket.socket, username: str, character: Dict, players: List, player_dict: Dict) -> None:
    """Main game loop for handling player commands."""
    try:
        while True:
            if not character.get('room'):
                character['room'] = "1"  # Reset to starting room if needed
                account_manager.update_character(username, character)

            client_socket.sendall(b"> ")
            command = receive_input(client_socket)
            
            if not command or command.lower() in ['exit', 'quit']:
                client_socket.sendall(b"Goodbye!\n")
                break

            # Handle the command
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
    """Clean up player session when they disconnect."""
    try:
        if character and username:
            # Remove from room
            room_vnum = character.get('room')
            if room_vnum:
                room_manager.remove_player_from_room(room_vnum, username)
                logging.debug(f"Removed player '{username}' from room {room_vnum}")

            # Remove from active players/characters
            account_manager.remove_connected_client(username)
            remove_player(username, players, players_lock)
            
            # Save final character state
            account_manager.update_character(username, character)
            
            logging.info(f"Successfully cleaned up session for player '{username}'")
            
    except Exception as e:
        logging.error(f"Error cleaning up session for '{username}': {e}")

def handle_client(client_socket: socket.socket, addr: tuple) -> None:
    """Handle new client connections and login process."""
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
                # Handle new account creation
                client_socket.sendall(b'Enter your desired account name: ')
                username = receive_input(client_socket)
                if not username:
                    break
                    
                username = username.lower()
                if account_manager.username_exists(username):
                    client_socket.sendall(b'Account already exists. Try again.\n')
                    continue

                client_socket.sendall(b'Enter your password: ')
                password = receive_input(client_socket)
                if not password:
                    break

                success, message = account_manager.create_account(username, password)
                if success:
                    client_socket.sendall(b'Account created successfully! Please log in.\n')
                    continue

            # Handle existing account login
            if account_manager.username_exists(account_choice.lower()):
                success, username, chosen_char = handle_login(client_socket, account_choice.lower())
                if success and username and chosen_char:
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

    except Exception as e:
        logging.error(f"Error handling client {addr}: {e}")
    finally:
        if username and chosen_char:
            cleanup_player_session(username, chosen_char)
        client_socket.close()

class GameServer:
    """Main game server class handling connections and server lifecycle."""
    
    def __init__(self, host: str, port: int, mob_manager: MobManager):
        self.host = host
        self.port = port
        self.mob_manager = mob_manager  # Add mob_manager as an attribute
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = False
        self.regeneration_thread = None
        # Remove spawn_manager creation
        
        # Add file paths for mob initialization
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
        """Start the regeneration thread."""
        self.regeneration_thread = threading.Thread(target=regeneration_loop, daemon=True)
        self.regeneration_thread.start()
        logging.info("Started regeneration thread")

    def initialize_game_state(self):
        """Initialize game state and clear any stale data."""
        try:
            # Clear connected players list
            with players_lock:
                players.clear()
            
            # Clear active characters
            with active_characters_lock:
                active_characters.clear()
            
            # Initialize rooms and clean up any stale player data
            room_manager.initialize_rooms()
            
            # First, clean all non-template mobs from rooms
            self.clean_mob_instances()
            
            # Then initialize mob spawning based on templates
            self.initialize_mobs()
            
            logging.info("Game state initialized successfully")
            return True
        except Exception as e:
            logging.critical(f"Failed to initialize game state: {e}")
            return False

    def clean_mob_instances(self):
        """Remove all non-template mob instances from rooms."""
        try:
            with open(self.file_paths["Room"], 'r') as f:
                rooms = json.load(f)
            
            for room in rooms:
                # Keep only template mobs
                room['mobs'] = [
                    mob for mob in room.get('mobs', [])
                    if mob.get('is_template', False)
                ]
            
            # Save cleaned rooms
            with open(self.file_paths["Room"], 'w') as f:
                json.dump(rooms, f, indent=4)
                
            logging.info("Cleaned all mob instances from rooms")
                
        except Exception as e:
            logging.error(f"Error cleaning mob instances: {e}")

    def initialize_mobs(self):
        """Initialize mob spawns based on templates."""
        try:
            # Remove this method entirely or change to:
            logging.info("Mob initialization handled by spawn manager")
            return True
        except Exception as e:
            logging.error(f"Error initializing mobs: {e}")

    def start(self):
        """Start the game server and begin accepting connections."""
        if not self.initialize_game_state():
            logging.critical("Failed to initialize game state. Server startup aborted.")
            return

        self.running = True
        self.start_regeneration()
        # Remove spawn_manager.start() line
        
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
                    if self.running:  # Only log if we're still supposed to be running
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
        """Stop the server and clean up all connections."""
        try:
            self.running = False
            self.spawn_manager.stop()  # Stop the mob spawn manager
            
            # Close all client connections
            with players_lock:
                for player in players:
                    try:
                        if player.get('socket'):
                            player['socket'].close()
                    except Exception as e:
                        logging.error(f"Error closing client socket: {e}")
                players.clear()

            # Clear active characters
            with active_characters_lock:
                active_characters.clear()

            # Close server socket
            try:
                self.server_socket.close()
            except Exception as e:
                logging.error(f"Error closing server socket: {e}")

            logging.info("Server shutdown complete")
            
        except Exception as e:
            logging.critical(f"Error during server shutdown: {e}")

def initialize_logging():
    """Initialize logging configuration."""
    try:
        # Create logs directory if it doesn't exist
        Path('logs').mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            filename='logs/server.log',
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler('logs/server.log'),
                logging.StreamHandler()  # Also log to console
            ]
        )
        logging.info("Logging initialized")
        return True
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        return False

def main():
    """Main entry point for the game server."""
    if not initialize_logging():
        print("Failed to initialize logging. Aborting startup.")
        return

    try:
        logging.info("Starting STAIR MUD server...")
        
        # Create data directories if they don't exist
        Path('game_data').mkdir(exist_ok=True)
        
        # Initialize server
        server = GameServer(HOST, PORT, mob_manager)  # Pass mob_manager to GameServer
        
        # Start the server
        server.start()
        
    except KeyboardInterrupt:
        logging.info("Server shutdown initiated by user.")
    except Exception as e:
        logging.critical(f"Critical error during server execution: {e}")
    finally:
        logging.info("Server shutdown complete.")

if __name__ == '__main__':
    main()



